from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Busca:
    origem: str
    destino: str
    data_ida: date
    data_volta: date | None = None
    adultos: int = 1
    classe: str = "economy"
    moeda: str = "BRL"


@dataclass
class Oferta:
    preco: Decimal
    companhia: str
    escalas: int
    provedor: str
    extras: dict = field(default_factory=dict)

    def como_dict(self):
        return {
            "preco": str(self.preco),
            "companhia": self.companhia,
            "escalas": self.escalas,
            "provedor": self.provedor,
            **self.extras,
        }


class ProvedorErro(Exception):
    """O provedor não conseguiu responder (bloqueio, mudança de layout, sem chave...)."""


class Provedor:
    nome = "base"

    def buscar(self, busca: Busca) -> list[Oferta]:
        """Devolve as ofertas encontradas ou levanta ProvedorErro."""
        raise NotImplementedError
