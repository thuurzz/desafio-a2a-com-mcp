"""Controllers do agente: orquestração do ciclo de reserva contra o servidor MCP.

Expõe o núcleo **assíncrono** (`executar_pedido`, `continuar`, `descobrir`) que a
fase 4 pluga no servidor A2A, mais o resultado tipado. As versões síncronas de
conveniência vivem em `agente.controllers.__init__` (via `asyncio.run`).

Nenhuma regra de negócio de sala aqui: conflito, política e alternativas são
decisão exclusiva do servidor MCP. O agente só traduz protocolo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mcp.types as types

from agente.controllers.parser import interpretar_pedido
from agente.models.pedido import Completado, Falhou, Pausado, Pedido, Resultado
from agente.views.cliente import ClienteMCP

OPCAO_RECUSAR = "recusar"


@dataclass(frozen=True)
class Descoberta:
    """Resultado da descoberta: nomes das tools e a versão da política."""

    tools: list[str]
    versao_politica: str


def _mensagem_de_erro(resultado: types.CallToolResult) -> str:
    for bloco in resultado.content or []:
        texto = getattr(bloco, "text", None)
        if texto:
            return texto
    return ""


def _traduzir(
    resultado: types.CallToolResult | types.InputRequiredResult,
    pedido: Pedido,
    versao_politica: str,
    traceparent: str | None,
) -> Resultado:
    if isinstance(resultado, types.InputRequiredResult):
        # Opaque: guarda o input_requests cru e o request_state sem abrir.
        return Pausado(
            pedido=pedido,
            versao_politica=versao_politica,
            input_requests=resultado.input_requests,
            request_state=resultado.request_state,
            traceparent=traceparent,
        )

    if resultado.is_error:
        return Falhou(mensagem=_mensagem_de_erro(resultado))

    dados: dict[str, Any] = resultado.structured_content or {}
    return Completado(
        reservado=bool(dados.get("reservado")),
        reserva=dados.get("reserva"),
        sala=dados.get("sala"),
        inicio=dados.get("inicio"),
        fim=dados.get("fim"),
        responsavel=dados.get("responsavel"),
        politica=versao_politica,
        motivo=dados.get("motivo"),
    )


async def descobrir(traceparent: str | None = None) -> Descoberta:
    """Descoberta em runtime: `tools/list` + `resources/read` da política."""
    async with ClienteMCP(traceparent=traceparent) as cliente:
        tools = await cliente.listar_tools()
        versao = await cliente.ler_politica()
    return Descoberta(tools=tools, versao_politica=versao)


async def executar_pedido(texto: str, traceparent: str | None = None) -> Resultado:
    """Executa um pedido fixo: descobre, lê a política e chama `reservar_sala`.

    Traduz o wire em resultado tipado: `complete` → `completado` (com a `politica`
    lida do resource), `input_required` → `pausado` (cru) e `isError` → `falhou`
    (mensagem exata). O `tools/list` acontece antes do primeiro `tools/call`.
    """
    pedido = interpretar_pedido(texto)
    async with ClienteMCP(traceparent=traceparent) as cliente:
        await cliente.listar_tools()
        versao = await cliente.ler_politica()
        resultado = await cliente.reservar(
            pedido.sala, pedido.inicio, pedido.fim, pedido.responsavel
        )
    return _traduzir(resultado, pedido, versao, traceparent)


async def continuar(task: Pausado, escolha: str) -> Resultado:
    """Continua uma pausa: refaz o `tools/call` com id novo + `inputResponses`.

    `escolha` é o id da sala alternativa, ou a sentinela `recusar` (→ `decline`).
    A chave de `inputResponses` é a **mesma chave única** que veio no
    `inputRequests`, e o `requestState` é ecoado byte a byte.
    """
    chave = next(iter(task.input_requests), None)
    if chave is None:
        return Falhou(mensagem="pausa sem inputRequests para responder")

    if escolha == OPCAO_RECUSAR:
        acao, conteudo = "decline", None
    else:
        acao, conteudo = "accept", {"sala": escolha}

    async with ClienteMCP(traceparent=task.traceparent) as cliente:
        resultado = await cliente.retomar(
            task.pedido.sala,
            task.pedido.inicio,
            task.pedido.fim,
            task.pedido.responsavel,
            chave,
            acao,
            conteudo,
            task.request_state,
        )
    return _traduzir(resultado, task.pedido, task.versao_politica, task.traceparent)


__all__ = [
    "interpretar_pedido",
    "executar_pedido",
    "continuar",
    "descobrir",
    "Descoberta",
]
