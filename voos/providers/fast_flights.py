import json
from decimal import Decimal

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

from .base import Busca, Oferta, Provedor, ProvedorErro

# Seções do payload do Google Voos: 2 = "melhores voos", 3 = "outros voos".
# O parser da biblioteca só lê a 3 e perde justamente os mais baratos, então lemos as duas aqui.
SECOES = (2, 3)


def extrair_ofertas(html: str, provedor: str) -> list[Oferta]:
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise ProvedorErro("página sem resultados (bloqueio ou mudança no Google Voos)")

    try:
        dados = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
        payload = json.loads(dados)
    except (IndexError, ValueError) as exc:
        raise ProvedorErro(f"resposta em formato inesperado: {exc}") from exc

    ofertas = []
    for indice in SECOES:
        secao = payload[indice] if len(payload) > indice else None
        if not secao or not secao[0]:
            continue
        for item in secao[0]:
            try:
                voo, preco = item[0], item[1][0][1]
                companhias, trechos = voo[1], voo[2]
            except (IndexError, TypeError):
                continue
            if not preco:
                continue
            ofertas.append(
                Oferta(
                    preco=Decimal(preco),
                    companhia=", ".join(companhias or []),
                    escalas=max(len(trechos or []) - 1, 0),
                    provedor=provedor,
                )
            )

    # Página válida mas sem nenhum voo acontece de forma intermitente, mesmo quando
    # existem voos: trata como falha para o próximo provedor tentar.
    if not ofertas:
        raise ProvedorErro("o Google Voos não retornou voos nesta tentativa")
    return ofertas


class FastFlightsProvedor(Provedor):
    """Lê o Google Voos direto pela biblioteca fast-flights. Grátis, mas não oficial."""

    nome = "fast_flights"

    def buscar(self, busca: Busca) -> list[Oferta]:
        trechos = [FlightQuery(date=busca.data_ida.isoformat(), from_airport=busca.origem, to_airport=busca.destino)]
        if busca.data_volta:
            trechos.append(
                FlightQuery(date=busca.data_volta.isoformat(), from_airport=busca.destino, to_airport=busca.origem)
            )

        query = create_query(
            flights=trechos,
            trip="round-trip" if busca.data_volta else "one-way",
            seat=busca.classe,
            passengers=Passengers(adults=busca.adultos),
            currency=busca.moeda,
            language="pt-BR",
        )

        try:
            html = fetch_flights_html(query)
        except Exception as exc:  # rede, TLS, timeout...
            raise ProvedorErro(f"{type(exc).__name__}: {exc}") from exc

        return extrair_ofertas(html, self.nome)
