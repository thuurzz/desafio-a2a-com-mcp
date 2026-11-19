"""Views do agente: servidor A2A (Agent Card + JSON-RPC) sobre Starlette.

Duas rotas, sem `fastapi` (decisão 1 do design): o card no well-known URI e o endpoint
JSON-RPC `/a2a`, que delega ao `ControladorA2A`. O `traceparent` do header HTTP é lido
aqui e repassado ao dispatcher, que o leva ao orquestrador (e daí ao `_meta` do MCP).
"""

from __future__ import annotations

import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agente.controllers.a2a import ControladorA2A

HOST_PADRAO = "127.0.0.1"
PORTA_PADRAO = 7300


def _configuracao() -> tuple[str, int]:
    """Host e porta do servidor A2A, parametrizáveis por env (default 7300)."""
    host = os.environ.get("A2A_HOST", HOST_PADRAO)
    porta = int(os.environ.get("A2A_PORT", str(PORTA_PADRAO)))
    return host, porta


def _url_do_endpoint() -> str:
    """URL do endpoint `/a2a`, derivada da mesma configuração de host/porta."""
    host, porta = _configuracao()
    return f"http://{host}:{porta}/a2a"


def _card() -> dict:
    """Agent Card v1.0, espelhando `exemplos/wire/07-a2a-agent-card.json`."""
    return {
        "name": "Central de Salas",
        "description": "Reserva salas de reuniao da Hill Valley Tech.",
        "provider": {
            "organization": "Hill Valley Tech",
            "url": "https://hillvalley.example",
        },
        "version": "1.0.0",
        "supportedInterfaces": [
            {
                "url": _url_do_endpoint(),
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "reservar-sala",
                "name": "Reservar sala",
                "description": (
                    "Reserva uma sala em um intervalo. Se houver conflito, pergunta "
                    "qual alternativa usar."
                ),
                "tags": ["salas", "agenda"],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
                "examples": [
                    "reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 "
                    "fim=2026-11-03T15:00:00-03:00 responsavel=Marty"
                ],
            }
        ],
    }


controlador = ControladorA2A()


async def rota_card(request: Request) -> JSONResponse:
    return JSONResponse(_card())


async def rota_a2a(request: Request) -> JSONResponse:
    corpo = await request.json()
    metodo = corpo.get("method")
    id_req = corpo.get("id")
    params = corpo.get("params") or {}
    traceparent = request.headers.get("traceparent")
    envelope = await controlador.tratar(metodo, id_req, params, traceparent)
    return JSONResponse(envelope)


app = Starlette(
    routes=[
        Route("/.well-known/agent-card.json", rota_card, methods=["GET"]),
        Route("/a2a", rota_a2a, methods=["POST"]),
    ]
)

__all__ = ["app", "_card", "_configuracao", "_url_do_endpoint"]
