import logging
import time
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.conf import settings

from .base import Busca, Oferta, Provedor, ProvedorErro

logger = logging.getLogger(__name__)

URL = "https://serpapi.com/search.json"
URL_CONTA = "https://serpapi.com/account.json"  # não consome cota
CACHE_COTA_SEGUNDOS = 600

CLASSES = {"economy": 1, "premium-economy": 2, "business": 3, "first": 4}


@dataclass
class Cota:
    restantes: int
    por_mes: int | None
    lido_em: float

    @property
    def no_limite(self) -> bool:
        return self.restantes <= settings.SERPAPI_RESERVA_MINIMA


# Cache por chave, para não consultar a conta a cada busca; cada busca feita
# desconta 1 localmente até a próxima leitura.
_cotas: dict[str, Cota] = {}


def limpar_cache_cota():
    _cotas.clear()


def consultar_cota(api_key: str | None = None, forcar: bool = False) -> Cota | None:
    """Buscas restantes no plano da SerpApi, ou None se não deu para saber."""
    api_key = api_key if api_key is not None else settings.SERPAPI_API_KEY
    if not api_key:
        return None
    cota = _cotas.get(api_key)
    if cota and not forcar and time.monotonic() - cota.lido_em < CACHE_COTA_SEGUNDOS:
        return cota
    try:
        dados = requests.get(URL_CONTA, params={"api_key": api_key}, timeout=30).json()
        restantes = int(dados["total_searches_left"])
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Não foi possível ler a cota da SerpApi: %s", exc)
        return cota  # último valor conhecido, se houver
    _cotas[api_key] = Cota(restantes=restantes, por_mes=dados.get("searches_per_month"), lido_em=time.monotonic())
    return _cotas[api_key]


class CotaNoLimite(ProvedorErro):
    """A cota da SerpApi chegou na reserva mínima: a busca nem é feita."""


class SerpApiProvedor(Provedor):
    """Google Flights via SerpApi. Estável, mas a cota grátis é pequena: fica como reserva."""

    nome = "serpapi"

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        self.api_key = api_key if api_key is not None else settings.SERPAPI_API_KEY
        self.timeout = timeout

    def buscar(self, busca: Busca) -> list[Oferta]:
        if not self.api_key:
            raise ProvedorErro("SERPAPI_API_KEY não configurada")

        cota = consultar_cota(self.api_key)
        if cota and cota.no_limite:
            raise CotaNoLimite(f"cota da SerpApi no limite ({cota.restantes} buscas restantes); reserva pausada")

        params = {
            "engine": "google_flights",
            "departure_id": busca.origem,
            "arrival_id": busca.destino,
            "outbound_date": busca.data_ida.isoformat(),
            "type": 1 if busca.data_volta else 2,
            "travel_class": CLASSES.get(busca.classe, 1),
            "adults": busca.adultos,
            "currency": busca.moeda,
            "hl": "pt",
            "gl": "br",
            "api_key": self.api_key,
        }
        if busca.data_volta:
            params["return_date"] = busca.data_volta.isoformat()

        try:
            resposta = requests.get(URL, params=params, timeout=self.timeout)
            dados = resposta.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProvedorErro(f"{type(exc).__name__}: {exc}") from exc

        if cota:
            cota.restantes -= 1

        if dados.get("error"):
            # "no results" não é falha do provedor; o resto (cota, chave inválida) é.
            if "hasn't returned any results" in dados["error"]:
                return []
            raise ProvedorErro(dados["error"])
        if resposta.status_code != 200:
            raise ProvedorErro(f"HTTP {resposta.status_code}")

        return self.converter(dados)

    def converter(self, dados: dict) -> list[Oferta]:
        ofertas = []
        for item in dados.get("best_flights", []) + dados.get("other_flights", []):
            if not item.get("price"):
                continue
            trechos = item.get("flights", [])
            companhias = list(dict.fromkeys(t.get("airline", "") for t in trechos if t.get("airline")))
            ofertas.append(
                Oferta(
                    preco=Decimal(str(item["price"])),
                    companhia=", ".join(companhias),
                    escalas=len(item.get("layovers", [])),
                    provedor=self.nome,
                )
            )
        return ofertas
