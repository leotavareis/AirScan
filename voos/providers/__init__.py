import logging
from dataclasses import dataclass, field

from django.conf import settings

from .base import Busca, Oferta, Provedor, ProvedorErro
from .fast_flights import FastFlightsProvedor
from .serpapi import SerpApiProvedor

logger = logging.getLogger(__name__)

REGISTRO: dict[str, type[Provedor]] = {
    FastFlightsProvedor.nome: FastFlightsProvedor,
    SerpApiProvedor.nome: SerpApiProvedor,
}


@dataclass
class Resultado:
    provedor: str | None
    ofertas: list[Oferta]
    erros: dict[str, str] = field(default_factory=dict)

    @property
    def sucesso(self):
        return self.provedor is not None


def provedores_configurados() -> list[Provedor]:
    return [REGISTRO[nome]() for nome in settings.AIRSCAN_PROVEDORES]


def buscar_com_fallback(busca: Busca, provedores: list[Provedor] | None = None) -> Resultado:
    """Tenta cada provedor na ordem; o primeiro que responder sem erro vence."""
    if provedores is None:
        provedores = provedores_configurados()

    erros = {}
    for provedor in provedores:
        try:
            ofertas = provedor.buscar(busca)
        except ProvedorErro as exc:
            logger.warning("Provedor %s falhou: %s", provedor.nome, exc)
            erros[provedor.nome] = str(exc)
            continue
        return Resultado(provedor=provedor.nome, ofertas=ofertas, erros=erros)

    return Resultado(provedor=None, ofertas=[], erros=erros)


__all__ = ["Busca", "Oferta", "Provedor", "ProvedorErro", "Resultado", "buscar_com_fallback"]
