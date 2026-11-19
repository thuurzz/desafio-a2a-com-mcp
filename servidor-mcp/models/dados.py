from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .tipos import Reserva, Sala

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "dados"


@dataclass(frozen=True)
class Dados:
    salas: list[Sala]
    reservas: list[Reserva]
    politica_texto: str
    politica_versao: str


def _ler_json(nome: str) -> list[dict]:
    return json.loads((DADOS / nome).read_text(encoding="utf-8"))


def _versao_politica(texto: str) -> str:
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    _, _, valor = primeira.partition(":")
    return valor.strip()


@lru_cache(maxsize=1)
def carregar() -> Dados:
    salas = [Sala.model_validate(item) for item in _ler_json("salas.json")]
    reservas = [Reserva.model_validate(item) for item in _ler_json("reservas.json")]
    politica_texto = (DADOS / "politica-de-uso.md").read_text(encoding="utf-8")
    return Dados(
        salas=salas,
        reservas=reservas,
        politica_texto=politica_texto,
        politica_versao=_versao_politica(politica_texto),
    )
