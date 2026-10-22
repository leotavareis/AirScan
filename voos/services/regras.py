from decimal import Decimal

ABAIXO_DO_ALVO = "abaixo_do_alvo"
QUEDA_PERCENTUAL = "queda_percentual"
MINIMO_HISTORICO = "minimo_historico"

DESCRICOES = {
    ABAIXO_DO_ALVO: "abaixo do preço alvo",
    QUEDA_PERCENTUAL: "caiu desde a última consulta",
    MINIMO_HISTORICO: "menor preço já visto",
}


def avaliar(
    preco: Decimal,
    *,
    preco_alvo: Decimal | None,
    queda_percentual: int,
    ultimo_preco: Decimal | None,
    minimo_historico: Decimal | None,
    preco_ultimo_alerta: Decimal | None,
) -> list[str]:
    """Devolve os motivos para avisar sobre `preco` (lista vazia = não avisar).

    Os preços de referência excluem a consulta atual. Para não repetir aviso,
    só alerta de novo quando o preço fica abaixo do último preço já avisado.
    """
    if preco_ultimo_alerta is not None and preco >= preco_ultimo_alerta:
        return []

    motivos = []
    if preco_alvo is not None and preco <= preco_alvo:
        motivos.append(ABAIXO_DO_ALVO)
    if queda_percentual and ultimo_preco:
        queda = (ultimo_preco - preco) / ultimo_preco * 100
        if queda >= queda_percentual:
            motivos.append(QUEDA_PERCENTUAL)
    if minimo_historico is not None and preco < minimo_historico:
        motivos.append(MINIMO_HISTORICO)
    return motivos
