from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from voos.services import telegram


class Command(BaseCommand):
    help = "Mostra o chat_id de quem falou com o bot e, se já configurado, envia uma mensagem de teste."

    def handle(self, *args, **opts):
        if not settings.TELEGRAM_CHAT_ID:
            try:
                chats = telegram.chats_recentes()
            except telegram.TelegramErro as exc:
                raise CommandError(str(exc))
            if not chats:
                raise CommandError("Nenhuma conversa encontrada. Mande qualquer mensagem para o bot e rode de novo.")
            self.stdout.write("Coloque um destes valores em TELEGRAM_CHAT_ID no .env:")
            for chat in chats:
                nome = chat.get("title") or chat.get("first_name") or chat.get("username") or ""
                self.stdout.write(f"  {chat['id']}  ({nome})")
            return

        if telegram.enviar("✅ AirScan conectado. Os alertas de preço vão chegar aqui."):
            self.stdout.write(self.style.SUCCESS("Mensagem de teste enviada."))
        else:
            raise CommandError("Não foi possível enviar; veja o erro acima.")
