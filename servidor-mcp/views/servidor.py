from __future__ import annotations

import json
from typing import Any

import mcp.types as types
from mcp.server.lowlevel.server import Server
from mcp.shared.exceptions import MCPError

from controllers.salas import consultar, listar_salas, reservar
from models.dados import carregar
from models.tipos import Disponibilidade, ListaDeSalas, ReservaOut

URI_POLITICA = "politica://uso"

# -32021: o cliente nao declarou a capability de elicitation em form mode.
CODIGO_SEM_CAPABILITY = -32021

# Chave atribuida pelo servidor ao pedido de escolha; o cliente a devolve igual
# no inputResponses do retry.
CHAVE_ESCOLHA = "escolha_de_sala"

MENSAGEM_ESCOLHA = "A sala pedida esta ocupada nesse intervalo. Escolha uma alternativa."
MOTIVO_RECUSA = "recusado"

DESCRICAO_LISTAR = "Lista todas as salas com capacidade e recursos."
DESCRICAO_CONSULTAR = "Diz se uma sala esta livre no intervalo, e quais reservas conflitam."
DESCRICAO_RESERVAR = "Reserva uma sala. Se o intervalo estiver ocupado, pergunta qual alternativa usar."

ENTRADA_LISTAR: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "title": "listar_salasArguments",
}

ENTRADA_CONSULTAR: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sala": {"title": "Sala", "type": "string"},
        "inicio": {"title": "Inicio", "type": "string"},
        "fim": {"title": "Fim", "type": "string"},
    },
    "required": ["sala", "inicio", "fim"],
    "title": "consultar_disponibilidadeArguments",
}

ENTRADA_RESERVAR: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sala": {"title": "Sala", "type": "string"},
        "inicio": {"title": "Inicio", "type": "string"},
        "fim": {"title": "Fim", "type": "string"},
        "responsavel": {"title": "Responsavel", "type": "string"},
    },
    "required": ["sala", "inicio", "fim", "responsavel"],
    "title": "reservar_salaArguments",
}

SAIDA_LISTAR = ListaDeSalas.model_json_schema()
SAIDA_CONSULTAR = Disponibilidade.model_json_schema()
SAIDA_RESERVAR = ReservaOut.model_json_schema()

TOOLS = [
    types.Tool(
        name="listar_salas",
        description=DESCRICAO_LISTAR,
        input_schema=ENTRADA_LISTAR,
        output_schema=SAIDA_LISTAR,
    ),
    types.Tool(
        name="consultar_disponibilidade",
        description=DESCRICAO_CONSULTAR,
        input_schema=ENTRADA_CONSULTAR,
        output_schema=SAIDA_CONSULTAR,
    ),
    types.Tool(
        name="reservar_sala",
        description=DESCRICAO_RESERVAR,
        input_schema=ENTRADA_RESERVAR,
        output_schema=SAIDA_RESERVAR,
    ),
]


def resultado_tool(payload: Any) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, indent=2),
            )
        ],
        structured_content=payload,
        is_error=False,
    )


def erro_tool(mensagem: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=mensagem)],
        is_error=True,
    )


def _schema_escolha(alternativas: list[str]) -> dict[str, Any]:
    """Schema plano restringindo a propriedade `sala` por enum, na ordem do controller."""
    return {
        "type": "object",
        "properties": {
            "sala": {
                "title": "Sala",
                "description": "Sala alternativa escolhida",
                "type": "string",
                "enum": alternativas,
            }
        },
        "required": ["sala"],
    }


def _tem_elicitation_form(ctx) -> bool:
    caps = ctx.session.client_capabilities
    return bool(caps and caps.elicitation and caps.elicitation.form)


def _erro_sem_capability() -> MCPError:
    return MCPError(
        code=CODIGO_SEM_CAPABILITY,
        message="Client did not declare elicitation capability in form mode",
        data=types.MissingRequiredClientCapabilityErrorData(
            required_capabilities=types.ClientCapabilities(elicitation={"form": {}})
        ).model_dump(by_alias=True, mode="json", exclude_none=True),
    )


def _concluir_retry(params: types.CallToolRequestParams) -> types.CallToolResult:
    """Conclui o ciclo MRTR a partir do requestState em texto claro (o boundary ja abriu).

    Reconstroi o pedido original do proprio estado selado e ignora params.arguments.
    """
    estado = json.loads(params.request_state)
    inicio = estado["inicio"]
    fim = estado["fim"]
    responsavel = estado["responsavel"]

    respostas = params.input_responses or {}
    resposta = next(iter(respostas.values()), None)
    acao = resposta.action if resposta is not None else None

    if acao in ("decline", "cancel"):
        return resultado_tool(
            {
                "reserva": None,
                "reservado": False,
                "sala": None,
                "inicio": None,
                "fim": None,
                "responsavel": None,
                "politica": None,
                "motivo": MOTIVO_RECUSA,
            }
        )

    conteudo = (resposta.content if resposta is not None else None) or {}
    sala_escolhida = conteudo.get("sala") or estado["sala"]
    resultado = reservar(sala_escolhida, inicio, fim, responsavel)
    if "erro" in resultado:
        return erro_tool(resultado["erro"])
    if "alternativas" in resultado:
        return erro_tool("Escolha fora das alternativas disponiveis no intervalo")
    return resultado_tool(resultado)


async def on_list_tools(ctx, params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def on_call_tool(ctx, params: types.CallToolRequestParams):
    nome = params.name
    argumentos = params.arguments or {}

    if nome == "listar_salas":
        return resultado_tool(listar_salas())

    if nome == "consultar_disponibilidade":
        resposta = consultar(
            argumentos.get("sala", ""),
            argumentos.get("inicio", ""),
            argumentos.get("fim", ""),
        )
        if "erro" in resposta:
            return erro_tool(resposta["erro"])
        return resultado_tool(resposta)

    if nome == "reservar_sala":
        # Retry do ciclo MRTR: o boundary ja verificou e abriu o requestState.
        if params.request_state is not None:
            return _concluir_retry(params)

        resposta = reservar(
            argumentos.get("sala", ""),
            argumentos.get("inicio", ""),
            argumentos.get("fim", ""),
            argumentos.get("responsavel", ""),
        )
        if "erro" in resposta:
            return erro_tool(resposta["erro"])
        if "alternativas" in resposta:
            if not _tem_elicitation_form(ctx):
                raise _erro_sem_capability()
            alternativas = resposta["alternativas"]
            pedido = {
                "sala": argumentos.get("sala", ""),
                "inicio": argumentos.get("inicio", ""),
                "fim": argumentos.get("fim", ""),
                "responsavel": argumentos.get("responsavel", ""),
                "alternativas": alternativas,
            }
            return types.InputRequiredResult(
                result_type="input_required",
                input_requests={
                    CHAVE_ESCOLHA: types.ElicitRequest(
                        params=types.ElicitRequestFormParams(
                            mode="form",
                            message=MENSAGEM_ESCOLHA,
                            requested_schema=_schema_escolha(alternativas),
                        )
                    )
                },
                request_state=json.dumps(pedido, ensure_ascii=False),
            )
        return resultado_tool(resposta)

    return erro_tool(f"Tool inexistente: {nome}")


async def on_list_resources(ctx, params) -> types.ListResourcesResult:
    return types.ListResourcesResult(
        resources=[
            types.Resource(
                uri=URI_POLITICA,
                name="politica-de-uso",
                description="Politica de uso das salas de reuniao.",
                mime_type="text/markdown",
            )
        ]
    )


async def on_read_resource(ctx, params: types.ReadResourceRequestParams):
    if params.uri != URI_POLITICA:
        raise MCPError(-32602, f"Resource inexistente: {params.uri}")
    return types.ReadResourceResult(
        contents=[
            types.TextResourceContents(
                uri=URI_POLITICA,
                mime_type="text/markdown",
                text=carregar().politica_texto,
            )
        ]
    )


def criar_servidor() -> Server:
    return Server(
        name="central-de-salas",
        version="1.0.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
        on_list_resources=on_list_resources,
        on_read_resource=on_read_resource,
    )
