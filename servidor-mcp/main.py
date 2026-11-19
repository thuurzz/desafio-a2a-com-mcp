from __future__ import annotations

import os

import uvicorn

from views.app import criar_app


def main() -> None:
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    porta = int(os.environ.get("MCP_PORT", "7301"))
    caminho = os.environ.get("MCP_PATH", "/mcp")
    app = criar_app(caminho)
    uvicorn.run(app, host=host, port=porta, log_level="info")


if __name__ == "__main__":
    main()
