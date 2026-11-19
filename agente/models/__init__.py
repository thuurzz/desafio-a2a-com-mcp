"""Modelos do agente: o pedido tipado e o resultado discriminado do ciclo de reserva."""

from .pedido import Completado, Falhou, Pausado, Pedido, Resultado

__all__ = ["Pedido", "Completado", "Pausado", "Falhou", "Resultado"]
