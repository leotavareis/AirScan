from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from voos.models import ConsultaPreco, Monitoramento
from voos.providers import serpapi


@override_settings(SERPAPI_API_KEY="", SERPAPI_RESERVA_MINIMA=20)
class ViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.client.force_login(self.user)
        self.ida = timezone.localdate() + timedelta(days=30)
        self.m = Monitoramento.objects.create(origem="GRU", destino="LIS", data_ida=self.ida, preco_alvo=Decimal(4000))

    def dados(self, **kw):
        base = {
            "origem": "gig",
            "destino": "mia",
            "data_ida": self.ida.isoformat(),
            "data_volta": (self.ida + timedelta(days=7)).isoformat(),
            "flex_dias": 1,
            "adultos": 1,
            "classe": "economy",
            "preco_alvo": "3500",
            "queda_percentual": 10,
            "ativo": "on",
        }
        base.update(kw)
        return base

    def test_exige_login(self):
        self.client.logout()
        r = self.client.get(reverse("voos:lista"))
        self.assertRedirects(r, f"{reverse('login')}?next=/")

    def test_lista_mostra_ultimo_preco(self):
        ConsultaPreco.objects.create(monitoramento=self.m, menor_preco=Decimal(3210), provedor="fast_flights")
        r = self.client.get(reverse("voos:lista"))
        self.assertContains(r, "GRU → LIS")
        self.assertContains(r, "R$ 3.210,00")

    def test_formulario_sugere_aeroportos(self):
        r = self.client.get(reverse("voos:criar"))
        self.assertContains(r, '<option value="IGU">Foz do Iguaçu · Foz do Iguaçu – Cataratas International Airport, BR</option>', html=True)
        self.assertGreater(r.content.count(b"<option value="), 3000)

    def test_criar(self):
        r = self.client.post(reverse("voos:criar"), self.dados())
        novo = Monitoramento.objects.get(destino="MIA")
        self.assertRedirects(r, reverse("voos:detalhe", args=[novo.pk]))
        self.assertEqual(novo.origem, "GIG")

    def test_validacoes(self):
        ontem = (timezone.localdate() - timedelta(days=1)).isoformat()
        r = self.client.post(reverse("voos:criar"), self.dados(origem="SP", data_ida=ontem, flex_dias=5))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.context["form"].errors), {"origem", "data_ida", "flex_dias"})

    def test_volta_antes_da_ida(self):
        r = self.client.post(reverse("voos:criar"), self.dados(data_volta=(self.ida - timedelta(days=1)).isoformat()))
        self.assertIn("data_volta", r.context["form"].errors)

    def test_editar(self):
        r = self.client.post(reverse("voos:editar", args=[self.m.pk]), self.dados(origem="GRU", destino="OPO"))
        self.assertRedirects(r, reverse("voos:detalhe", args=[self.m.pk]))
        self.m.refresh_from_db()
        self.assertEqual(self.m.destino, "OPO")

    def test_excluir(self):
        self.client.post(reverse("voos:excluir", args=[self.m.pk]))
        self.assertFalse(Monitoramento.objects.exists())

    def test_pausar(self):
        self.client.post(reverse("voos:alternar", args=[self.m.pk]))
        self.m.refresh_from_db()
        self.assertFalse(self.m.ativo)

    def test_detalhe_com_grafico(self):
        ConsultaPreco.objects.create(monitoramento=self.m, menor_preco=Decimal(3210), provedor="fast_flights")
        ConsultaPreco.objects.create(monitoramento=self.m, sucesso=False, erro="bloqueado")
        r = self.client.get(reverse("voos:detalhe", args=[self.m.pk]))
        self.assertContains(r, 'id="dados-grafico"')
        self.assertEqual(r.context["grafico"]["precos"], [3210.0])
        self.assertContains(r, "Falhou em todos os provedores")

    def test_checar_agora_sem_voos(self):
        def executar(ms):
            ConsultaPreco.objects.create(monitoramento=ms[0], provedor="fast_flights")
            return {"consultas": 1, "falhas": 0, "alertas": 0, "desativados": 0}

        with mock.patch("voos.views.coletor.executar", side_effect=executar):
            r = self.client.post(reverse("voos:checar", args=[self.m.pk]), follow=True)
        self.assertContains(r, "não mostrou nenhum voo")
        self.assertContains(r, "Nenhum voo encontrado para essas datas")

    def test_checar_agora(self):
        def executar(ms):
            ConsultaPreco.objects.create(monitoramento=ms[0], menor_preco=Decimal(2999), provedor="fast_flights")
            return {"consultas": 1, "falhas": 0, "alertas": 1, "desativados": 0}

        with mock.patch("voos.views.coletor.executar", side_effect=executar):
            r = self.client.post(reverse("voos:checar", args=[self.m.pk]), follow=True)
        self.assertContains(r, "R$ 2.999,00")
        self.assertContains(r, "alerta enviado")

    def test_lista_mostra_cota(self):
        with mock.patch("voos.views.serpapi.consultar_cota", return_value=serpapi.Cota(243, 250, 0)):
            self.assertContains(self.client.get(reverse("voos:lista")), "243 de 250 buscas restantes")
        with mock.patch("voos.views.serpapi.consultar_cota", return_value=serpapi.Cota(12, 250, 0)):
            self.assertContains(self.client.get(reverse("voos:lista")), "Reserva SerpApi pausada")
