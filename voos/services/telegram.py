import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{metodo}"


class TelegramErro(Exception):
    pass


def _chamar(metodo: str, **params) -> dict:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramErro("TELEGRAM_BOT_TOKEN não configurado")
    try:
        resposta = requests.post(API.format(token=token, metodo=metodo), json=params, timeout=30)
        dados = resposta.json()
    except (requests.RequestException, ValueError) as exc:
        raise TelegramErro(f"{type(exc).__name__}: {exc}") from exc
    if not dados.get("ok"):
        raise TelegramErro(dados.get("description", f"HTTP {resposta.status_code}"))
    return dados


def enviar(texto: str) -> bool:
    """Envia uma mensagem para o chat configurado. Devolve False se não deu."""
    if not settings.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID não configurado; mensagem não enviada:\n%s", texto)
        return False
    try:
        _chamar(
            "sendMessage",
            chat_id=settings.TELEGRAM_CHAT_ID,
            text=texto,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except TelegramErro as exc:
        logger.error("Falha ao enviar para o Telegram: %s", exc)
        return False
    return True


def chats_recentes() -> list[dict]:
    """Chats que mandaram mensagem ao bot recentemente (para descobrir o chat_id)."""
    dados = _chamar("getUpdates")
    chats = {}
    for update in dados.get("result", []):
        mensagem = update.get("message") or update.get("channel_post") or {}
        chat = mensagem.get("chat")
        if chat:
            chats[chat["id"]] = chat
    return list(chats.values())
