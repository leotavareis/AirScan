import logging
import random
import time
from datetime import timedelta
from html import escape
from urllib.parse import quote

from django.conf import settings
from django.db.models import Min
from django.utils import timezone

from voos.models import Alerta, AvisoSistema, ConsultaPreco, Monitoramento
from voos.providers import Busca, buscar_com_fallback, serpapi

from . import regras, telegram

logger = logging.getLogger(__name__)


def datas_candidatas(m: Monitoramento):
    """Pares (ida, volta) a buscar; com flex, desloca ida e volta juntas."""
    hoje = timezone.localdate()
    pares = []
    for delta in range(-m.flex_dias, m.flex_dias + 1):
        ida = m.data_ida + timedelta(days=delta)
        if ida < hoje:
            continue
        volta = m.data_volta + timedelta(days=delta) if m.data_volta else None
        pares.append((ida, volta))
    return pares


def _pausar():
    time.sleep(random.uniform(settings.AIRSCAN_PAUSA_MIN, settings.AIRSCAN_PAUSA_MAX))


def consultar(m: Monitoramento, buscar=buscar_com_fallback) -> ConsultaPreco:
    """Busca todas as datas do monitoramento e grava o menor preço encontrado."""
    melhor = None  # (oferta, ida, volta)
    provedores_usados = set()
    erros = {}
    top = []

    for i, (ida, volta) in enumerate(datas_candidatas(m)):
        if i:
            _pausar()
        busca = Busca(
            origem=m.origem,
            destino=m.destino,
            data_ida=ida,
            data_volta=volta,
            adultos=m.adultos,
            classe=m.classe,
            moeda=settings.AIRSCAN_MOEDA,
        )
        resultado = buscar(busca)
        for nome, erro in resultado.erros.items():
            erros[f"{ida} {nome}"] = erro
        if not resultado.sucesso:
            continue
        provedores_usados.add(resultado.provedor)
        for oferta in resultado.ofertas:
            top.append({**oferta.como_dict(), "data_ida": ida.isoformat()})
            if melhor is None or oferta.preco < melhor[0].preco:
                melhor = (oferta, ida, volta)

    top.sort(key=lambda o: float(o["preco"]))
    consulta = ConsultaPreco(
        monitoramento=m,
        moeda=settings.AIRSCAN_MOEDA,
        provedor=",".join(sorted(provedores_usados)),
        sucesso=bool(provedores_usados),
        erro="\n".join(f"{k}: {v}" for k, v in erros.items()),
        dados_brutos={"ofertas": top[:10]},
    )
    if melhor:
        oferta, ida, volta = melhor
        consulta.menor_preco = oferta.preco
        consulta.companhia = oferta.companhia
        consulta.escalas = oferta.escalas
        consulta.data_ida = ida
        consulta.data_volta = volta
    consulta.save()
    return consulta


def avaliar_consulta(consulta: ConsultaPreco) -> Alerta | None:
    if consulta.menor_preco is None:
        return None
    m = consulta.monitoramento
    anteriores = m.consultas.filter(menor_preco__isnull=False).exclude(pk=consulta.pk)
    ultima = anteriores.order_by("-consultado_em").first()
    ultimo_alerta = m.alertas.select_related("consulta").order_by("-criado_em").first()

    motivos = regras.avaliar(
        consulta.menor_preco,
        preco_alvo=m.preco_alvo,
        queda_percentual=m.queda_percentual,
        ultimo_preco=ultima.menor_preco if ultima else None,
        minimo_historico=anteriores.aggregate(v=Min("menor_preco"))["v"],
        preco_ultimo_alerta=ultimo_alerta.consulta.menor_preco if ultimo_alerta else None,
    )
    if not motivos:
        return None
    return Alerta.objects.create(monitoramento=m, consulta=consulta, motivos=motivos)


def link_google_voos(consulta: ConsultaPreco) -> str:
    m = consulta.monitoramento
    texto = f"Flights to {m.destino} from {m.origem} on {consulta.data_ida}"
    if consulta.data_volta:
        texto += f" through {consulta.data_volta}"
    return f"https://www.google.com/travel/flights?q={quote(texto)}&curr={consulta.moeda}&hl=pt-BR"


def formatar_preco(valor, moeda="BRL") -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}" if moeda == "BRL" else f"{moeda} {texto}"


def mensagem_alerta(alerta: Alerta) -> str:
    c = alerta.consulta
    m = alerta.monitoramento
    datas = f"{c.data_ida:%d/%m/%Y}" + (f" ↔ {c.data_volta:%d/%m/%Y}" if c.data_volta else " (só ida)")
    motivos = "; ".join(regras.DESCRICOES.get(x, x) for x in alerta.motivos)
    escalas = "direto" if c.escalas == 0 else f"{c.escalas} escala(s)"
    linhas = [
        f"✈️ <b>{m.origem} → {m.destino}</b> por <b>{formatar_preco(c.menor_preco, c.moeda)}</b>",
        f"📅 {datas}",
        f"🛫 {escape(c.companhia or '?')} — {escalas}",
        f"📉 {motivos}",
    ]
    if m.preco_alvo:
        linhas.append(f"🎯 alvo: {formatar_preco(m.preco_alvo, c.moeda)}")
    linhas.append(f'<a href="{link_google_voos(c)}">Ver no Google Voos</a>')
    return "\n".join(linhas)


def desativar_vencidos() -> int:
    return Monitoramento.objects.filter(ativo=True, data_ida__lt=timezone.localdate()).update(ativo=False)


def executar(monitoramentos=None, buscar=buscar_com_fallback, notificar=telegram.enviar) -> dict:
    """Roda todos os monitoramentos ativos: consulta, avalia e avisa."""
    resumo = {"desativados": desativar_vencidos(), "consultas": 0, "falhas": 0, "alertas": 0}
    if monitoramentos is None:
        monitoramentos = Monitoramento.objects.filter(ativo=True)

    for i, m in enumerate(monitoramentos):
        if i:
            _pausar()
        consulta = consultar(m, buscar=buscar)
        resumo["consultas"] += 1
        if not consulta.sucesso:
            resumo["falhas"] += 1
            logger.error("Todos os provedores falharam para %s:\n%s", m, consulta.erro)
            continue
        logger.info("%s: menor preço %s (%s)", m, consulta.menor_preco, consulta.provedor)

        alerta = avaliar_consulta(consulta)
        if alerta:
            alerta.enviado = notificar(mensagem_alerta(alerta))
            alerta.save(update_fields=["enviado"])
            resumo["alertas"] += 1

    hoje = timezone.localdate()
    if resumo["falhas"]:
        avisar_uma_vez(
            f"falhas-{hoje:%Y-%m-%d}",
            f"⚠️ AirScan: {resumo['falhas']} de {resumo['consultas']} consultas falharam em todos os provedores. "
            "Veja o histórico das rotas. (Este aviso sai no máximo uma vez por dia.)",
            notificar,
        )

    cota = serpapi.consultar_cota() if "serpapi" in settings.AIRSCAN_PROVEDORES else None
    if cota and cota.no_limite:
        resumo["cota_serpapi_no_limite"] = True
        total = f" de {cota.por_mes}" if cota.por_mes else ""
        avisar_uma_vez(
            f"serpapi-cota-{hoje:%Y-%m}",
            f"⚠️ AirScan: a cota da SerpApi está quase no fim ({cota.restantes}{total} buscas restantes). "
            "A reserva foi pausada até a cota renovar; o fast-flights continua funcionando. "
            "Rotas em que só a SerpApi acha voos ficam sem preço até lá.",
            notificar,
        )
    return resumo


def avisar_uma_vez(chave: str, texto: str, notificar) -> bool:
    """Envia o aviso só se ainda não foi enviado com esta chave."""
    if AvisoSistema.objects.filter(chave=chave).exists():
        return False
    if not notificar(texto):
        return False
    AvisoSistema.objects.create(chave=chave)
    return True
