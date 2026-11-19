from __future__ import annotations

import json
import logging
import sys
from typing import Any

CHAVE_PROTOCOLO = "io.modelcontextprotocol/protocolVersion"
CHAVE_CAPACIDADES = "io.modelcontextprotocol/clientCapabilities"

logger = logging.getLogger("servidor-mcp.requests")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_request(metodo: Any, id_request: Any, traceparent: Any) -> None:
    metodo_txt = "-" if metodo is None else str(metodo)
    id_txt = "-" if id_request is None else str(id_request)
    trace_txt = "-" if traceparent is None or traceparent == "" else str(traceparent)
    logger.info("mcp request metodo=%s id=%s traceparent=%s", metodo_txt, id_txt, trace_txt)


async def _ler_corpo(receive) -> bytes:
    corpo = b""
    while True:
        mensagem = await receive()
        if mensagem["type"] != "http.request":
            break
        corpo += mensagem.get("body", b"")
        if not mensagem.get("more_body", False):
            break
    return corpo


async def _responder_erro(send, id_request: Any, mensagem: str) -> None:
    corpo = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": id_request,
            "error": {"code": -32602, "message": mensagem},
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(corpo)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": corpo})


class GuardaMetaMiddleware:
    def __init__(self, app, caminho: str = "/mcp") -> None:
        self.app = app
        self.caminho = caminho

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST" or scope.get("path") != self.caminho:
            await self.app(scope, receive, send)
            return

        corpo = await _ler_corpo(receive)
        try:
            dados = json.loads(corpo)
        except (json.JSONDecodeError, UnicodeDecodeError):
            dados = None

        if not isinstance(dados, dict):
            log_request(None, None, None)
            enviado = False

            async def receber_bruto():
                nonlocal enviado
                if not enviado:
                    enviado = True
                    return {"type": "http.request", "body": corpo, "more_body": False}
                return await receive()

            await self.app(scope, receber_bruto, send)
            return

        metodo = dados.get("method")
        id_request = dados.get("id")
        params = dados.get("params")
        meta = params.get("_meta") if isinstance(params, dict) else None
        traceparent = meta.get("traceparent") if isinstance(meta, dict) else None

        log_request(metodo, id_request, traceparent)

        if not isinstance(meta, dict) or CHAVE_PROTOCOLO not in meta or CHAVE_CAPACIDADES not in meta:
            await _responder_erro(
                send,
                id_request,
                "Invalid params: _meta requires io.modelcontextprotocol/protocolVersion "
                "and io.modelcontextprotocol/clientCapabilities",
            )
            return

        enviado = False

        async def receber_replay():
            nonlocal enviado
            if not enviado:
                enviado = True
                return {"type": "http.request", "body": corpo, "more_body": False}
            return await receive()

        await self.app(scope, receber_replay, send)
