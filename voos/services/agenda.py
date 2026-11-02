from datetime import datetime, timedelta

from django.db import IntegrityError
from django.utils import timezone

from voos.models import Agenda, AvisoSistema

# O timer da VM chama a checagem agendada a cada 5 minutos. Um horário vale até
# JANELA depois dele; se a VM estava fora do ar por mais tempo, ele é pulado.
JANELA = timedelta(hours=1)


def horario_devido(agora=None):
    """O horário da agenda que deveria rodar agora e ainda não rodou (ou None).

    Devolve a chave que marca a execução, ex.: "agenda-2026-11-02-0705".
    """
    agora = agora or timezone.localtime()
    hoje = agora.date()
    devidos = []
    for dia in (hoje - timedelta(days=1), hoje):
        for h in Agenda.atual().horarios():
            inicio = datetime.combine(dia, h, tzinfo=agora.tzinfo)
            if inicio <= agora < inicio + JANELA:
                devidos.append((inicio, f"agenda-{dia:%Y-%m-%d}-{h:%H%M}"))
    for _, chave in sorted(devidos, reverse=True):
        if not AvisoSistema.objects.filter(chave=chave).exists():
            return chave
    return None


def marcar(chave: str) -> bool:
    """Marca o horário como executado. False se outro processo já marcou."""
    try:
        AvisoSistema.objects.create(chave=chave)
    except IntegrityError:
        return False
    return True


def proximo_horario(agora=None):
    """Data e hora da próxima checagem agendada (ou None se a agenda estiver vazia)."""
    agora = agora or timezone.localtime()
    horarios = Agenda.atual().horarios()
    for dia in (agora.date(), agora.date() + timedelta(days=1)):
        for h in horarios:
            inicio = datetime.combine(dia, h, tzinfo=agora.tzinfo)
            if inicio > agora:
                return inicio
    return None
