from django.conf import settings
from django.core.management.base import BaseCommand

from voos.models import Monitoramento
from voos.services import agenda, coletor


class Command(BaseCommand):
    help = "Consulta os preços dos monitoramentos ativos e avisa no Telegram quando baixarem."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, action="append", help="Só estes monitoramentos (pode repetir)")
        parser.add_argument("--sem-notificar", action="store_true", help="Não envia nada ao Telegram")
        parser.add_argument(
            "--agendado",
            action="store_true",
            help="Só roda se chegou um dos horários definidos no site (usado pelo timer a cada 5 min)",
        )

    def handle(self, *args, **opts):
        if opts["agendado"]:
            chave = agenda.horario_devido()
            if chave is None or not agenda.marcar(chave):
                return
            self.stdout.write(f"Checagem agendada ({chave}).")

        monitoramentos = None
        if opts["id"]:
            monitoramentos = Monitoramento.objects.filter(pk__in=opts["id"])

        kwargs = {}
        if settings.AIRSCAN_RESUMO_CONSULTAS:
            kwargs["enviar_resumo"] = coletor.enviar_resumo
        if opts["sem_notificar"]:
            kwargs["notificar"] = lambda texto: self.stdout.write(f"[não enviado]\n{texto}\n") or False
            if "enviar_resumo" in kwargs:
                kwargs["enviar_resumo"] = kwargs["notificar"]

        resumo = coletor.executar(monitoramentos, **kwargs)
        self.stdout.write(
            self.style.SUCCESS(
                f"{resumo['consultas']} consulta(s), {resumo['falhas']} falha(s), "
                f"{resumo['alertas']} alerta(s), {resumo['desativados']} monitoramento(s) vencido(s) desativado(s)."
            )
        )
