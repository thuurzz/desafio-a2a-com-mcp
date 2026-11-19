"""Tipos do agente: `Pedido` e o resultado discriminado do ciclo de reserva.

O resultado tem três formas — `completado`, `pausado` e `falhou` — modeladas como
dataclasses congeladas. O `requestState` e o `inputRequests` guardados no `pausado`
são **opacos**: o agente os guarda e ecoa, nunca abre, interpreta nem reconstrói.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Pedido:
    """Pedido de reserva interpretado por regra a partir do formato fixo."""

    sala: str
    inicio: str
    fim: str
    responsavel: str


@dataclass(frozen=True)
class Completado:
    """Reserva concluída (criada ou recusada). `reservado=False` marca a recusa."""

    reservado: bool
    reserva: str | None
    sala: str | None
    inicio: str | None
    fim: str | None
    responsavel: str | None
    politica: str
    motivo: str | None


@dataclass(frozen=True)
class Pausado:
    """Pausa por `input_required`: guarda o pedido e o estado cru do MRTR.

    `input_requests` e `request_state` são opacos: a única leitura mecânica é a
    **chave única** de `input_requests`, exigida para montar o `inputResponses` do
    retry. `versao_politica` já lida do resource acompanha o pedido para que a
    continuação não precise relê-la.
    """

    pedido: Pedido
    versao_politica: str
    input_requests: dict[str, Any]
    request_state: str | None
    traceparent: str | None


@dataclass(frozen=True)
class Falhou:
    """Falha de execução da tool, com a mensagem exata devolvida pelo servidor."""

    mensagem: str


Resultado = Completado | Pausado | Falhou
