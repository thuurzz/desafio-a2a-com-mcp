#!/usr/bin/env python3
"""Script que exercita o ciclo completo do agente como host MCP.

Descobre as tools e o resource, reserva um intervalo livre, provoca um conflito
(que pausa em `input_required`) e continua a pausa com uma escolha — e também com
a recusa. É o entrypoint que a fase 3 usa para provar o gate no stderr do servidor:
`tools/list` antes do primeiro `tools/call`, e o `traceparent` propagado.

Uso:

    .venv/bin/python agente/main.py [--traceparent 00-<trace-id>-<span-id>-01]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Garante que `agente.*` resolva também quando rodado como arquivo (`python agente/main.py`).
_RAIZ = Path(__file__).resolve().parents[1]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from agente.controllers import (  # noqa: E402
    continuar_async,
    descobrir_async,
    executar_pedido_async,
)
from agente.models.pedido import Completado, Falhou, Pausado  # noqa: E402


def _rotulo(resultado) -> str:
    if isinstance(resultado, Completado):
        return f"completado(reservado={resultado.reservado}, sala={resultado.sala}, politica={resultado.politica})"
    if isinstance(resultado, Pausado):
        return f"pausado(chaves={list(resultado.input_requests)})"
    if isinstance(resultado, Falhou):
        return f"falhou(mensagem={resultado.mensagem!r})"
    return repr(resultado)


async def _ciclo(traceparent: str | None) -> None:
    descoberta = await descobrir_async(traceparent=traceparent)
    print(f"tools: {descoberta.tools}")
    print(f"politica: {descoberta.versao_politica}")

    livre = await executar_pedido_async(
        "reservar sala=sala-porao inicio=2026-11-03T09:00:00-03:00 "
        "fim=2026-11-03T10:00:00-03:00 responsavel=Doc",
        traceparent=traceparent,
    )
    print(f"reserva livre -> {_rotulo(livre)}")

    pausado = await executar_pedido_async(
        "reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 "
        "fim=2026-11-03T15:00:00-03:00 responsavel=Marty",
        traceparent=traceparent,
    )
    print(f"reserva em conflito -> {_rotulo(pausado)}")

    if isinstance(pausado, Pausado):
        aceito = await continuar_async(pausado, "sala-fusca")
        print(f"continuar(sala-fusca) -> {_rotulo(aceito)}")

        recusavel = await executar_pedido_async(
            "reservar sala=sala-garagem inicio=2026-11-03T14:30:00-03:00 "
            "fim=2026-11-03T15:30:00-03:00 responsavel=Biff",
            traceparent=traceparent,
        )
        print(f"reserva recusavel -> {_rotulo(recusavel)}")
        if isinstance(recusavel, Pausado):
            recusado = await continuar_async(recusavel, "recusar")
            print(f"continuar(recusar) -> {_rotulo(recusado)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercita o ciclo do agente como host MCP")
    parser.add_argument("--traceparent", help="traceparent da chamada de entrada (opcional)")
    parser.add_argument("--url", help="URL do servidor MCP (default http://127.0.0.1:7301/mcp)")
    args = parser.parse_args()

    if args.url:
        import os

        os.environ["MCP_URL"] = args.url

    asyncio.run(_ciclo(args.traceparent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
