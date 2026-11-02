import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from voos.models import Alerta, AvisoSistema, ConsultaPreco, Monitoramento
from voos.providers import Busca, Oferta, Provedor, ProvedorErro, Resultado, buscar_com_fallback
from voos.providers.fast_flights import FastFlightsProvedor
from voos.providers import serpapi
from voos.providers.serpapi import CotaNoLimite, SerpApiProvedor
from voos.services import coletor, regras

D = Decimal


class ProvedorFalso(Provedor):
    def __init__(self, nome, ofertas=None, erro=None):
        self.nome = nome
        self.ofertas = ofertas or []
        self.erro = erro
        self.chamadas = 0

    def buscar(self, busca):
        self.chamadas += 1
        if self.erro:
            raise ProvedorErro(self.erro)
        return self.ofertas


def busca_exemplo():
    return Busca(origem="GRU", destino="LIS", data_ida=timezone.localdate() + timedelta(days=30))


class FallbackTests(SimpleTestCase):
    def test_usa_primeiro_que_responde(self):
        a = ProvedorFalso("a", [Oferta(D(100), "X", 0, "a")])
        b = ProvedorFalso("b", [Oferta(D(90), "Y", 0, "b")])
        r = buscar_com_fallback(busca_exemplo(), [a, b])
        self.assertEqual(r.provedor, "a")
        self.assertEqual(b.chamadas, 0)

    def test_cai_para_o_segundo(self):
        a = ProvedorFalso("a", erro="bloqueado")
        b = ProvedorFalso("b", [Oferta(D(90), "Y", 0, "b")])
        r = buscar_com_fallback(busca_exemplo(), [a, b])
        self.assertEqual(r.provedor, "b")
        self.assertEqual(r.erros, {"a": "bloqueado"})

    def test_todos_falham(self):
        r = buscar_com_fallback(busca_exemplo(), [ProvedorFalso("a", erro="x"), ProvedorFalso("b", erro="y")])
        self.assertFalse(r.sucesso)
        self.assertEqual(set(r.erros), {"a", "b"})

    @staticmethod
    def pagina(melhores, outros):
        def secao(itens):
            if not itens:
                return None
            return [[[[["XX"], [cia], [{}] * (escalas + 1)], [[None, preco]]] for preco, cia, escalas in itens]]

        payload = [None, None, secao(melhores), secao(outros)] + [None] * 4
        return f'<script class="ds:1">AF_initDataCallback({{key: "ds:1", data:{json.dumps(payload)}, sideChannel: {{}}}});</script>'

    def buscar_pagina(self, html):
        with mock.patch("voos.providers.fast_flights.fetch_flights_html", return_value=html):
            return FastFlightsProvedor().buscar(busca_exemplo())

    def test_fast_flights_le_melhores_e_outros(self):
        ofertas = self.buscar_pagina(self.pagina([(1901, "Azul", 2)], [(3810, "LATAM", 1)]))
        self.assertEqual([(o.preco, o.companhia, o.escalas) for o in ofertas], [(D(1901), "Azul", 2), (D(3810), "LATAM", 1)])

    def test_fast_flights_so_melhores(self):
        self.assertEqual(len(self.buscar_pagina(self.pagina([(1901, "Azul", 0)], None))), 1)

    def test_fast_flights_pagina_sem_voos_e_falha(self):
        with self.assertRaises(ProvedorErro):
            self.buscar_pagina(self.pagina(None, None))

    def test_fast_flights_pagina_sem_resultados_e_bloqueio(self):
        with self.assertRaises(ProvedorErro):
            self.buscar_pagina("<html>captcha</html>")

    def test_fast_flights_erro_de_rede_vira_erro(self):
        with mock.patch("voos.providers.fast_flights.fetch_flights_html", side_effect=OSError("timeout")):
            with self.assertRaises(ProvedorErro):
                FastFlightsProvedor().buscar(busca_exemplo())

    def test_fast_flights_sem_voos_usa_reserva(self):
        reserva = ProvedorFalso("serpapi", [Oferta(D(1901), "Azul", 2, "serpapi")])
        with mock.patch("voos.providers.fast_flights.fetch_flights_html", return_value=self.pagina(None, None)):
            r = buscar_com_fallback(busca_exemplo(), [FastFlightsProvedor(), reserva])
        self.assertEqual((r.provedor, reserva.chamadas), ("serpapi", 1))


def resposta_json(dados, status=200):
    return mock.Mock(status_code=status, json=lambda: dados)


CONTA = {"total_searches_left": 243, "searches_per_month": 250}
VOOS = {"best_flights": [{"price": 1901, "flights": [{"airline": "Azul"}]}]}


@override_settings(SERPAPI_RESERVA_MINIMA=20)
class SerpApiTests(SimpleTestCase):
    def setUp(self):
        serpapi.limpar_cache_cota()

    def test_cota_e_lida_uma_vez_e_descontada(self):
        with mock.patch("voos.providers.serpapi.requests.get", side_effect=[resposta_json(CONTA), resposta_json(VOOS), resposta_json(VOOS)]) as get:
            p = SerpApiProvedor(api_key="k")
            p.buscar(busca_exemplo())
            p.buscar(busca_exemplo())
        urls = [c.args[0] for c in get.call_args_list]
        self.assertEqual(urls.count(serpapi.URL_CONTA), 1)
        self.assertEqual(serpapi.consultar_cota("k").restantes, 241)

    def test_para_de_buscar_no_limite(self):
        with mock.patch("voos.providers.serpapi.requests.get", return_value=resposta_json({**CONTA, "total_searches_left": 20})) as get:
            with self.assertRaises(CotaNoLimite):
                SerpApiProvedor(api_key="k").buscar(busca_exemplo())
        self.assertEqual(get.call_count, 1)  # só a leitura da conta, nenhuma busca

    def test_sem_conseguir_ler_cota_continua_buscando(self):
        with mock.patch("voos.providers.serpapi.requests.get", side_effect=[resposta_json({"error": "x"}), resposta_json(VOOS)]):
            self.assertEqual(len(SerpApiProvedor(api_key="k").buscar(busca_exemplo())), 1)

    def test_sem_chave_e_erro(self):
        with self.assertRaises(ProvedorErro):
            SerpApiProvedor(api_key="").buscar(busca_exemplo())

    def test_converter(self):
        dados = {
            "best_flights": [
                {
                    "price": 3210,
                    "flights": [{"airline": "TAP"}, {"airline": "TAP"}],
                    "layovers": [{"name": "Porto"}],
                }
            ],
            "other_flights": [{"price": 4000, "flights": [{"airline": "LATAM"}]}, {"flights": []}],
        }
        ofertas = SerpApiProvedor(api_key="k").converter(dados)
        self.assertEqual([(o.preco, o.companhia, o.escalas) for o in ofertas], [(D(3210), "TAP", 1), (D(4000), "LATAM", 0)])

    def test_erro_de_cota(self):
        erro = resposta_json({"error": "Your account has run out of searches."}, 429)
        with mock.patch("voos.providers.serpapi.requests.get", side_effect=[resposta_json(CONTA), erro]):
            with self.assertRaises(ProvedorErro):
                SerpApiProvedor(api_key="k").buscar(busca_exemplo())


class RegrasTests(SimpleTestCase):
    def avaliar(self, preco, **kw):
        base = dict(preco_alvo=None, queda_percentual=10, ultimo_preco=None, minimo_historico=None, preco_ultimo_alerta=None)
        base.update(kw)
        return regras.avaliar(D(preco), **base)

    def test_primeira_consulta_so_avisa_pelo_alvo(self):
        self.assertEqual(self.avaliar(3000), [])
        self.assertEqual(self.avaliar(3000, preco_alvo=D(3500)), [regras.ABAIXO_DO_ALVO])

    def test_queda_percentual(self):
        self.assertIn(regras.QUEDA_PERCENTUAL, self.avaliar(900, ultimo_preco=D(1000)))
        self.assertNotIn(regras.QUEDA_PERCENTUAL, self.avaliar(950, ultimo_preco=D(1000)))
        self.assertNotIn(regras.QUEDA_PERCENTUAL, self.avaliar(500, ultimo_preco=D(1000), queda_percentual=0))

    def test_minimo_historico(self):
        self.assertIn(regras.MINIMO_HISTORICO, self.avaliar(990, ultimo_preco=D(1000), minimo_historico=D(1000)))

    def test_nao_repete_aviso_sem_nova_queda(self):
        self.assertEqual(self.avaliar(3000, preco_alvo=D(3500), preco_ultimo_alerta=D(3000)), [])
        self.assertEqual(self.avaliar(2900, preco_alvo=D(3500), preco_ultimo_alerta=D(3000)), [regras.ABAIXO_DO_ALVO])


@override_settings(AIRSCAN_PAUSA_MIN=0, AIRSCAN_PAUSA_MAX=0, SERPAPI_API_KEY="")
class ColetorTests(TestCase):
    def setUp(self):
        self.m = Monitoramento.objects.create(
            origem="gru", destino="lis", data_ida=timezone.localdate() + timedelta(days=30), preco_alvo=D(3000)
        )
        self.enviadas = []

    def notificar(self, texto):
        self.enviadas.append(texto)
        return True

    def rodar(self, *precos, provedor="fast_flights"):
        def buscar(busca):
            return Resultado(provedor, [Oferta(D(p), "TAP", 0, provedor) for p in precos])

        return coletor.executar(buscar=buscar, notificar=self.notificar)

    def test_codigos_em_maiusculas(self):
        self.assertEqual((self.m.origem, self.m.destino), ("GRU", "LIS"))

    def test_grava_menor_preco_e_avisa_abaixo_do_alvo(self):
        self.rodar(3500, 2800, 3100)
        consulta = ConsultaPreco.objects.get()
        self.assertEqual(consulta.menor_preco, D(2800))
        self.assertEqual(Alerta.objects.get().motivos, [regras.ABAIXO_DO_ALVO])
        self.assertEqual(len(self.enviadas), 1)
        self.assertIn("R$ 2.800,00", self.enviadas[0])
        self.assertIn("google.com/travel/flights", self.enviadas[0])

    def test_sem_spam_quando_preco_nao_cai_de_novo(self):
        self.rodar(2800)
        self.rodar(2800)
        self.rodar(2900)
        self.assertEqual(Alerta.objects.count(), 1)
        self.rodar(2500)
        self.assertEqual(Alerta.objects.count(), 2)

    def test_falha_total_grava_erro_e_avisa(self):
        def buscar(busca):
            return Resultado(None, [], {"fast_flights": "bloqueado", "serpapi": "sem chave"})

        resumo = coletor.executar(buscar=buscar, notificar=self.notificar)
        self.assertEqual(resumo["falhas"], 1)
        consulta = ConsultaPreco.objects.get()
        self.assertFalse(consulta.sucesso)
        self.assertIn("bloqueado", consulta.erro)
        self.assertIn("falharam", self.enviadas[-1])

    def test_desativa_vencidos(self):
        Monitoramento.objects.create(origem="GRU", destino="REC", data_ida=timezone.localdate() - timedelta(days=1))
        resumo = self.rodar(5000)
        self.assertEqual(resumo["desativados"], 1)
        self.assertEqual(resumo["consultas"], 1)

    def test_flex_busca_datas_vizinhas(self):
        self.m.flex_dias = 2
        self.m.data_volta = self.m.data_ida + timedelta(days=7)
        self.m.save()
        pares = coletor.datas_candidatas(self.m)
        self.assertEqual(len(pares), 5)
        self.assertTrue(all((volta - ida).days == 7 for ida, volta in pares))

    def test_aviso_de_falha_sai_uma_vez_por_dia(self):
        def buscar(busca):
            return Resultado(None, [], {"fast_flights": "bloqueado"})

        coletor.executar(buscar=buscar, notificar=self.notificar)
        coletor.executar(buscar=buscar, notificar=self.notificar)
        self.assertEqual(sum("falharam" in t for t in self.enviadas), 1)

    @override_settings(SERPAPI_RESERVA_MINIMA=20)
    def test_avisa_cota_no_limite_uma_vez_por_mes(self):
        cota = serpapi.Cota(restantes=15, por_mes=250, lido_em=0)
        with mock.patch("voos.services.coletor.serpapi.consultar_cota", return_value=cota):
            resumo = self.rodar(3500)
            self.rodar(3500)
        self.assertTrue(resumo["cota_serpapi_no_limite"])
        avisos = [t for t in self.enviadas if "cota da SerpApi" in t]
        self.assertEqual(len(avisos), 1)
        self.assertIn("15 de 250", avisos[0])
        self.assertTrue(AvisoSistema.objects.filter(chave__startswith="serpapi-cota-").exists())

    def test_alerta_de_alvo_tem_destaque(self):
        self.rodar(2800)
        self.assertIn("PREÇO ALVO ATINGIDO", self.enviadas[0])
        self.assertIn("R$ 200,00 abaixo", self.enviadas[0])

    def test_alerta_sem_alvo_nao_tem_destaque(self):
        self.rodar(5000)
        self.rodar(4000)  # caiu 20%, mas continua acima do alvo
        self.assertEqual(Alerta.objects.get().motivos, [regras.QUEDA_PERCENTUAL, regras.MINIMO_HISTORICO])
        self.assertNotIn("PREÇO ALVO ATINGIDO", self.enviadas[0])

    def rodar_com_resumo(self, *precos):
        resumos = []

        def buscar(busca):
            return Resultado("fast_flights", [Oferta(D(p), "TAP", 0, "fast_flights") for p in precos])

        coletor.executar(
            buscar=buscar, notificar=self.notificar, enviar_resumo=lambda t: resumos.append(t) or True
        )
        return resumos

    def test_resumo_sai_a_cada_checagem_mesmo_sem_alerta(self):
        self.assertEqual(self.rodar_com_resumo(5000), [mock.ANY])
        resumo = self.rodar_com_resumo(5100)[0]
        self.assertEqual(self.enviadas, [])  # sem alerta: preço subiu e está acima do alvo
        self.assertIn("checagem das", resumo)
        self.assertIn("GRU → LIS", resumo)
        self.assertIn("R$ 5.100,00", resumo)
        self.assertIn("▲ R$ 100,00 (2,0%)", resumo)
        self.assertIn("faltam R$ 2.100,00", resumo)
        self.assertIn("menor já visto R$ 5.000,00", resumo)

    def test_resumo_primeira_consulta_e_no_alvo(self):
        resumo = self.rodar_com_resumo(2900)[0]
        self.assertIn("primeira consulta", resumo)
        self.assertIn("🎯 no alvo", resumo)

    def test_resumo_mostra_falha(self):
        resumos = []
        coletor.executar(
            buscar=lambda b: Resultado(None, [], {"fast_flights": "bloqueado"}),
            notificar=self.notificar,
            enviar_resumo=resumos.append,
        )
        self.assertIn("nenhum provedor respondeu", resumos[0])

    def test_sem_resumo_por_padrao(self):
        # Sem enviar_resumo, executar() só manda os alertas.
        self.rodar(5000)
        self.assertEqual(self.enviadas, [])

    def test_aviso_nao_marcado_se_telegram_falhar(self):
        self.assertFalse(coletor.avisar_uma_vez("x", "texto", lambda t: False))
        self.assertTrue(coletor.avisar_uma_vez("x", "texto", self.notificar))
        self.assertFalse(coletor.avisar_uma_vez("x", "texto", self.notificar))
