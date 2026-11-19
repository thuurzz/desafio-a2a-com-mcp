"""Interpretação determinística do pedido de reserva, por regra (sem LLM).

O formato é fixo:

    reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>

A interpretação é um `re.fullmatch` sobre os quatro campos `chave=valor`, sem
nenhum componente de modelo de linguagem no caminho. Dado o mesmo texto, o mesmo
`Pedido` sai — determinismo garantido por construção.
"""

from __future__ import annotations

import re

from agente.models.pedido import Pedido

# Campos separados por espaço, na ordem fixa do enunciado. Os valores não contêm
# espaço (id de sala, ISO-8601 e nome), então `\S+` é suficiente e determinístico.
_PADRAO = re.compile(
    r"reservar\s+"
    r"sala=(?P<sala>\S+)\s+"
    r"inicio=(?P<inicio>\S+)\s+"
    r"fim=(?P<fim>\S+)\s+"
    r"responsavel=(?P<responsavel>\S+)"
)


def interpretar_pedido(texto: str) -> Pedido:
    """Interpreta o pedido fixo e devolve um `Pedido` tipado.

    Levanta `ValueError` quando o texto não casa com o formato fixo; o servidor
    MCP é quem valida sala, horário e política — o agente só traduz o texto.
    """
    if not isinstance(texto, str):
        raise ValueError("pedido deve ser texto")
    casou = _PADRAO.fullmatch(texto.strip())
    if casou is None:
        raise ValueError(
            "pedido fora do formato fixo: "
            "reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>"
        )
    return Pedido(
        sala=casou["sala"],
        inicio=casou["inicio"],
        fim=casou["fim"],
        responsavel=casou["responsavel"],
    )
