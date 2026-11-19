from __future__ import annotations

import json
import logging
import sys
from typing import Any

CHAVE_PROTOCOLO = "io.modelcontextprotocol/protocolVersion"
CHAVE_CAPACIDADES = "io.modelcontextprotocol/clientCapabilities"

# Códigos JSON-RPC que o enunciado exige que respondam com HTTP 400.
CODIGOS_HTTP_400 = (-32021, -32602)

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


def _eh_erro_protocolo(corpo: bytes) -> bool:
    """True quando o corpo JSON-RPC traz um error.code que exige HTTP 400."""
    try:
        dados = json.loads(corpo)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    erro = dados.get("error") if isinstance(dados, dict) else None
    return isinstance(erro, dict) and erro.get("code") in CODIGOS_HTTP_400


class GuardaMetaMiddleware:
    def __init__(self, app, caminho: str = "/mcp") -> None:
        self.app = app
        self.caminho = caminho

    async def _encaminhar(self, scope, receive, send) -> None:
        """Encaminha ao app bufferizando a resposta e reescrevendo o status HTTP.

        O corpo JSON-RPC so e conhecido depois que o transporte responde; aqui o
        http.response.start fica retido e o status vira 400 quando o JSON-RPC
        traz error.code em -32021/-32602.
        """
        status = 200
        cabecalhos: list[tuple[bytes, bytes]] = []
        corpo = b""

        async def send_bufferizado(mensagem: dict) -> None:
            nonlocal status, cabecalhos, corpo
            tipo = mensagem.get("type")
            if tipo == "http.response.start":
                status = mensagem.get("status", 200)
                cabecalhos = mensagem.get("headers", [])
                return
            if tipo == "http.response.body":
                corpo += mensagem.get("body", b"")
                if not mensagem.get("more_body", False):
                    status_final = 400 if _eh_erro_protocolo(corpo) else status
                    cabecalhos_final = [
                        (n, v)
                        for n, v in cabecalhos
                        if n.lower() not in (b"content-length", b"transfer-encoding")
                    ]
                    cabecalhos_final.append((b"content-length", str(len(corpo)).encode()))
                    await send(
                        {
                            "type": "http.response.start",
                            "status": status_final,
                            "headers": cabecalhos_final,
                        }
                    )
                    await send({"type": "http.response.body", "body": corpo})
                return
            await send(mensagem)

        await self.app(scope, receive, send_bufferizado)

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

        await self._encaminhar(scope, receber_replay, send)
