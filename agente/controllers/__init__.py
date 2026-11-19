"""Controllers do agente: a biblioteca interna que a fase 4 pluga no servidor A2A.

Interface síncrona (conveniência para scripts e verificações) e o núcleo
assíncrono (`*_async`) para o servidor A2A da fase 4, que já roda num event loop.

- `interpretar_pedido(texto)` → `Pedido` (determinístico, sem LLM)
- `executar_pedido(texto, traceparent=None)` → `Resultado`
- `continuar(task, escolha)` → `Resultado`
- `descobrir(traceparent=None)` → `Descoberta`
"""

from __future__ import annotations

import asyncio

from agente.controllers import orquestrador as _orq
from agente.controllers.parser import interpretar_pedido
from agente.models.pedido import Completado, Falhou, Pausado, Pedido, Resultado

# Núcleo assíncrono, para a fase 4 (servidor A2A) usar sem `asyncio.run` aninhado.
executar_pedido_async = _orq.executar_pedido
continuar_async = _orq.continuar
descobrir_async = _orq.descobrir


def executar_pedido(texto: str, traceparent: str | None = None) -> Resultado:
    return asyncio.run(_orq.executar_pedido(texto, traceparent))


def continuar(task: Pausado, escolha: str) -> Resultado:
    return asyncio.run(_orq.continuar(task, escolha))


def descobrir(traceparent: str | None = None):
    return asyncio.run(_orq.descobrir(traceparent))


__all__ = [
    "interpretar_pedido",
    "executar_pedido",
    "continuar",
    "descobrir",
    "executar_pedido_async",
    "continuar_async",
    "descobrir_async",
    "Pedido",
    "Completado",
    "Pausado",
    "Falhou",
    "Resultado",
]
