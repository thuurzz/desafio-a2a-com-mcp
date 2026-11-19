from __future__ import annotations

import os

from .middleware import GuardaMetaMiddleware
from .servidor import criar_servidor as montar_servidor


def criar_servidor():
    return montar_servidor()


def criar_app(caminho: str | None = None):
    caminho = caminho or os.environ.get("MCP_PATH", "/mcp")
    servidor = montar_servidor()
    app = servidor.streamable_http_app(
        streamable_http_path=caminho,
        stateless_http=True,
        json_response=True,
    )
    app.add_middleware(GuardaMetaMiddleware, caminho=caminho)
    return app
