"""Views do agente: o cliente MCP Streamable HTTP.

O transporte é o cliente oficial do SDK (`streamable_http_client` + `ClientSession`).
Três pontos resolvem o desafio, todos verificados na versão instalada:

- `ClientSession.call_tool(..., allow_input_required=True, meta={...})` devolve o
  `InputRequiredResult` **cru** — o SDK não roda o driver de MRTR nem o callback de
  elicitation, então a pausa chega inteira ao controller.
- `RequestParamsMeta` é um TypedDict aberto: a chave extra `traceparent` viaja no
  `_meta` junto dos campos reservados `io.modelcontextprotocol/*`.
- O `ClientSession` monta os headers do transporte a partir do corpo: `Mcp-Method`
  (o método), `Mcp-Name` (nome da tool em `tools/call`, URI em `resources/read`) e
  `MCP-Protocol-Version` — exatamente o espelhamento que o enunciado exige. Não há
  transporte fino: o SDK já produz o wire correto.
"""

from __future__ import annotations

import os
import secrets
from contextlib import AsyncExitStack
from typing import Any

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL_PADRAO = "http://127.0.0.1:7301/mcp"
URI_POLITICA = "politica://uso"
NOME_CLIENTE = "agente-central-de-salas"
VERSAO_CLIENTE = "1.0.0"
NOME_TOOL_RESERVAR = "reservar_sala"


async def _recusar_elicitation(context: Any, params: Any) -> types.ElicitResult:
    """Callback que apenas anuncia a capability de elicitation em form mode.

    Com `allow_input_required=True` o SDK devolve o `InputRequiredResult` cru e este
    callback **nunca roda**; ele existe só para que `_build_capabilities` anuncie
    `{"elicitation": {"form": {}}}` no `_meta`. Retornar `decline` é o gesto seguro
    caso algum caminho inesperado o invoque: o agente nunca auto-responde.
    """
    return types.ElicitResult(action="decline")


def _extrair_trace_id(traceparent: str | None) -> str | None:
    """Extrai o trace-id (preservado) de um `traceparent`; `None` quando ausente."""
    if not traceparent:
        return None
    partes = str(traceparent).split("-")
    if len(partes) >= 2 and partes[0] == "00":
        return partes[1]
    return None


def _extrair_versao(texto: str) -> str:
    """Versão da política: a primeira linha `versao: <valor>`."""
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    _, _, valor = primeira.partition(":")
    return valor.strip()


class ClienteMCP:
    """Cliente MCP vivo: transporte + cache da versão da política entre chamadas.

    Mantém o objeto de transporte (nada de sessão nem estado de protocolo) e o
    cache da versão lida do resource. Cada request carrega o próprio `_meta` com
    `protocolVersion`, `clientCapabilities` (elicitation form), `clientInfo` e,
    quando há `traceparent` de entrada, o `traceparent` propagado com o mesmo
    trace-id e span-id novo.
    """

    def __init__(self, url: str | None = None, traceparent: str | None = None) -> None:
        self._url = url or os.environ.get("MCP_URL", URL_PADRAO)
        self._trace_id = _extrair_trace_id(traceparent)
        self._versao_politica: str | None = None
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    def _traceparent(self) -> str | None:
        if self._trace_id is None:
            return None
        return f"00-{self._trace_id}-{secrets.token_hex(8)}-01"

    def _meta(self) -> dict[str, str]:
        meta: dict[str, str] = {}
        traceparent = self._traceparent()
        if traceparent is not None:
            meta["traceparent"] = traceparent
        return meta

    async def __aenter__(self) -> "ClienteMCP":
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(streamable_http_client(self._url))
        self._session = await self._stack.enter_async_context(
            ClientSession(
                read,
                write,
                client_info=types.Implementation(name=NOME_CLIENTE, version=VERSAO_CLIENTE),
                elicitation_callback=_recusar_elicitation,
            )
        )
        # Negocia a revisão moderna (2026-07-28) e instala o stamp que injeta
        # `_meta` completo e os headers `Mcp-*` em todo request seguinte.
        await self._session.discover()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._stack is not None:
            await self._stack.aclose()

    def _sessao(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("cliente MCP não conectado")
        return self._session

    async def listar_tools(self) -> list[str]:
        """Descoberta em runtime (`tools/list`) — nenhum catálogo hardcoded."""
        sessao = self._sessao()
        resultado = await sessao.list_tools(params=types.PaginatedRequestParams(meta=self._meta()))
        return [tool.name for tool in resultado.tools]

    async def ler_politica(self) -> str:
        """Lê `politica://uso` e devolve a versão da primeira linha (com cache)."""
        if self._versao_politica is not None:
            return self._versao_politica
        sessao = self._sessao()
        resultado = await sessao.read_resource(URI_POLITICA, meta=self._meta())
        texto = resultado.contents[0].text
        self._versao_politica = _extrair_versao(texto)
        return self._versao_politica

    async def reservar(
        self, sala: str, inicio: str, fim: str, responsavel: str
    ) -> types.CallToolResult | types.InputRequiredResult:
        sessao = self._sessao()
        return await sessao.call_tool(
            NOME_TOOL_RESERVAR,
            {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel},
            meta=self._meta(),
            allow_input_required=True,
        )

    async def retomar(
        self,
        sala: str,
        inicio: str,
        fim: str,
        responsavel: str,
        chave: str,
        acao: str,
        conteudo: dict[str, Any] | None,
        request_state: str | None,
    ) -> types.CallToolResult | types.InputRequiredResult:
        """Retry do ciclo MRTR: `tools/call` com id novo, `inputResponses` e o
        `requestState` ecoado byte a byte. O SDK gera um id JSON-RPC novo a cada
        `send_request`, então o id do retry difere do request inicial."""
        sessao = self._sessao()
        resposta = types.ElicitResult(action=acao, content=conteudo)
        return await sessao.call_tool(
            NOME_TOOL_RESERVAR,
            {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel},
            input_responses={chave: resposta},
            request_state=request_state,
            meta=self._meta(),
            allow_input_required=True,
        )
