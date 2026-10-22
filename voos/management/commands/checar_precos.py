from django.core.management.base import BaseCommand

from voos.models import Monitoramento
from voos.services import coletor


class Command(BaseCommand):
    help = "Consulta os preços dos monitoramentos ativos e avisa no Telegram quando baixarem."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, action="append", help="Só estes monitoramentos (pode repetir)")
        parser.add_argument("--sem-notificar", action="store_true", help="Não envia nada ao Telegram")

    def handle(self, *args, **opts):
        monitoramentos = None
        if opts["id"]:
            monitoramentos = Monitoramento.objects.filter(pk__in=opts["id"])

        kwargs = {}
        if opts["sem_notificar"]:
            kwargs["notificar"] = lambda texto: self.stdout.write(f"[não enviado]\n{texto}\n") or False

        resumo = coletor.executar(monitoramentos, **kwargs)
        self.stdout.write(
            self.style.SUCCESS(
                f"{resumo['consultas']} consulta(s), {resumo['falhas']} falha(s), "
                f"{resumo['alertas']} alerta(s), {resumo['desativados']} monitoramento(s) vencido(s) desativado(s)."
            )
        )
