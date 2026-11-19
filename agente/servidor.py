#!/usr/bin/env python3
"""Entrypoint do servidor A2A (fase 4): sobe o uvicorn na porta configurada.

Host e porta vêm de env (`A2A_HOST` / `A2A_PORT`, defaults `127.0.0.1` e `7300`),
e a `url` do Agent Card é derivada da mesma configuração (ver `agente/views/a2a.py`).

Uso:

    A2A_PORT=7300 .venv/bin/python agente/servidor.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que `agente.*` resolva também quando rodado como arquivo (`python agente/servidor.py`).
_RAIZ = Path(__file__).resolve().parents[1]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import uvicorn  # noqa: E402

from agente.views.a2a import _configuracao, app  # noqa: E402


def main() -> None:
    host, porta = _configuracao()
    uvicorn.run(app, host=host, port=porta)


if __name__ == "__main__":
    main()
