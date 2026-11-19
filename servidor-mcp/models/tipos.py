from __future__ import annotations

from pydantic import BaseModel


class Sala(BaseModel):
    id: str
    nome: str
    capacidade: int
    recursos: list[str]


class Reserva(BaseModel):
    id: str
    sala: str
    inicio: str
    fim: str
    responsavel: str


class ConflitoOut(BaseModel):
    id: str
    inicio: str
    fim: str
    responsavel: str


class ListaDeSalas(BaseModel):
    salas: list[Sala]


class Disponibilidade(BaseModel):
    sala: str
    livre: bool
    conflitos: list[ConflitoOut]


class ReservaOut(BaseModel):
    reserva: str | None = None
    reservado: bool = True
    sala: str | None = None
    inicio: str | None = None
    fim: str | None = None
    responsavel: str | None = None
    politica: str | None = None
    motivo: str | None = None
