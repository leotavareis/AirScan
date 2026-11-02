from datetime import datetime, time
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from voos.models import Agenda, AvisoSistema
from voos.services import agenda

SP = ZoneInfo("America/Sao_Paulo")


def em(dia, hora, minuto):
    return datetime(2026, 11, dia, hora, minuto, tzinfo=SP)


class AgendaTests(TestCase):
    def test_padrao_tem_tres_horarios(self):
        self.assertEqual(Agenda.atual().horarios(), [time(7, 5), time(13, 10), time(20, 15)])

    def test_antes_do_horario_nao_roda(self):
        self.assertIsNone(agenda.horario_devido(em(2, 7, 0)))

    def test_roda_uma_vez_por_horario(self):
        chave = agenda.horario_devido(em(2, 7, 5))
        self.assertEqual(chave, "agenda-2026-11-02-0705")
        self.assertTrue(agenda.marcar(chave))
        self.assertIsNone(agenda.horario_devido(em(2, 7, 10)))
        self.assertFalse(agenda.marcar(chave))

    def test_atraso_dentro_da_janela_ainda_roda(self):
        self.assertEqual(agenda.horario_devido(em(2, 7, 50)), "agenda-2026-11-02-0705")

    def test_atraso_fora_da_janela_e_pulado(self):
        self.assertIsNone(agenda.horario_devido(em(2, 8, 10)))

    def test_horario_perto_da_meia_noite(self):
        a = Agenda.atual()
        a.horario_3 = time(23, 50)
        a.save()
        self.assertEqual(agenda.horario_devido(em(3, 0, 10)), "agenda-2026-11-02-2350")

    def test_campos_vazios_checam_menos_vezes(self):
        a = Agenda.atual()
        a.horario_2 = a.horario_3 = None
        a.save()
        self.assertEqual(a.horarios(), [time(7, 5)])
        self.assertIsNone(agenda.horario_devido(em(2, 13, 10)))

    def test_proximo_horario(self):
        self.assertEqual(agenda.proximo_horario(em(2, 14, 0)), em(2, 20, 15))
        self.assertEqual(agenda.proximo_horario(em(2, 21, 0)), em(3, 7, 5))

    def test_comando_agendado_so_roda_no_horario(self):
        with mock.patch("voos.services.coletor.executar", return_value={
            "consultas": 0, "falhas": 0, "alertas": 0, "desativados": 0,
        }) as executar:
            with mock.patch("voos.services.agenda.timezone.localtime", return_value=em(2, 6, 0)):
                call_command("checar_precos", "--agendado", stdout=StringIO())
            executar.assert_not_called()
            with mock.patch("voos.services.agenda.timezone.localtime", return_value=em(2, 7, 6)):
                call_command("checar_precos", "--agendado", stdout=StringIO())
                call_command("checar_precos", "--agendado", stdout=StringIO())
            executar.assert_called_once()
        self.assertTrue(AvisoSistema.objects.filter(chave="agenda-2026-11-02-0705").exists())


class AgendaViewTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("u", password="p"))

    def test_salva_horarios(self):
        r = self.client.post(reverse("voos:agenda"), {"horario_1": "06:30", "horario_2": "", "horario_3": "22:00"})
        self.assertRedirects(r, reverse("voos:lista"))
        self.assertEqual(Agenda.atual().horarios(), [time(6, 30), time(22, 0)])
        r = self.client.get(reverse("voos:lista"))
        self.assertContains(r, "06:30, 22:00")

    def test_recusa_horarios_repetidos(self):
        r = self.client.post(reverse("voos:agenda"), {"horario_1": "07:00", "horario_2": "07:00", "horario_3": ""})
        self.assertContains(r, "precisam ser diferentes")
        self.assertEqual(Agenda.atual().horario_1, time(7, 5))

    def test_exige_login(self):
        self.client.logout()
        r = self.client.get(reverse("voos:agenda"))
        self.assertEqual(r.status_code, 302)
