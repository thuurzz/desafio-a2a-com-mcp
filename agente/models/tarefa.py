"""Modelo da Task A2A: estados, mensagens, artifact e serialização para o wire.

Esta é a metade de fora do agente (fase 4): a `Task` que o servidor A2A devolve em
`SendMessage` e `GetTask`, com a máquina de estados `SUBMITTED → WORKING → terminal`
e o artifact `reserva`. A serialização (`para_dict`) espelha `exemplos/wire/08..10`:
`status` é `{state, message}`, `history` é uma lista de mensagens e `artifacts` é uma
lista de objetos `{artifactId, name, parts}`.

Os ids (`task-<hex12>`, `ctx-<hex12>`, `msg-<hex12>`, `art-<hex12>`) seguem o formato
dos exemplos de wire e são gerados com `secrets.token_hex(6)`.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from enum import Enum


class EstadoTask(str, Enum):
    """Estados da Task A2A v1.0 (o `.value` é o nome exato do wire)."""

    SUBMETIDA = "TASK_STATE_SUBMITTED"
    TRABALHANDO = "TASK_STATE_WORKING"
    CONCLUIDA = "TASK_STATE_COMPLETED"
    FALHOU = "TASK_STATE_FAILED"
    CANCELADA = "TASK_STATE_CANCELED"
    # Não-terminal: uma Task pausada por `input_required` ainda aceita `SendMessage`
    # de continuação (`escolha=...`). Fica fora de `ESTADOS_TERMINAIS` por isso.
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"


# Estados terminais: a Task nunca volta a `WORKING` a partir deles. `INPUT_REQUIRED`
# é intencionalmente excluído — a pausa é retomável (fase 5, decisão 1 do design).
ESTADOS_TERMINAIS = frozenset(
    {EstadoTask.CONCLUIDA, EstadoTask.FALHOU, EstadoTask.CANCELADA}
)


def novo_id(prefixo: str) -> str:
    """Gera um id no formato `<prefixo>-<hex12>` (ex.: `task-3f658e57d468`)."""
    return f"{prefixo}-{secrets.token_hex(6)}"


def artifact_reserva(
    reserva: str,
    sala: str,
    inicio: str,
    fim: str,
    responsavel: str,
    politica: str,
) -> str:
    """Serializa o conteúdo do artifact `reserva` como JSON com as seis chaves exatas."""
    dados = {
        "reserva": reserva,
        "sala": sala,
        "inicio": inicio,
        "fim": fim,
        "responsavel": responsavel,
        "politica": politica,
    }
    return json.dumps(dados, ensure_ascii=False)


@dataclass
class Mensagem:
    """Uma mensagem da Task no wire A2A (`ROLE_USER` ou `ROLE_AGENT`)."""

    messageId: str
    role: str
    parts: list[dict[str, str]]
    taskId: str | None = None
    contextId: str | None = None

    def para_dict(self) -> dict:
        dados: dict = {
            "messageId": self.messageId,
            "role": self.role,
            "parts": self.parts,
        }
        if self.taskId is not None:
            dados["taskId"] = self.taskId
        if self.contextId is not None:
            dados["contextId"] = self.contextId
        return dados


@dataclass
class Artifact:
    """Um artifact da Task (ex.: a reserva concluída, `name == "reserva"`)."""

    artifactId: str
    name: str
    parts: list[dict[str, str]]

    def para_dict(self) -> dict:
        return {
            "artifactId": self.artifactId,
            "name": self.name,
            "parts": self.parts,
        }


@dataclass
class Status:
    """O `status` da Task: `{state, message}` (a mensagem do agente, quando houver)."""

    estado: EstadoTask
    mensagem: Mensagem | None = None

    def para_dict(self) -> dict:
        return {
            "state": self.estado.value,
            "message": self.mensagem.para_dict() if self.mensagem is not None else None,
        }


@dataclass
class Task:
    """Uma Task A2A, registrada em memória pelo id (decisão 2 do design)."""

    id: str
    contextId: str
    status: Status
    history: list[Mensagem] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)

    def eh_terminal(self) -> bool:
        return self.status.estado in ESTADOS_TERMINAIS

    def para_dict(self) -> dict:
        return {
            "id": self.id,
            "contextId": self.contextId,
            "status": self.status.para_dict(),
            "history": [m.para_dict() for m in self.history],
            "artifacts": [a.para_dict() for a in self.artifacts],
        }


__all__ = [
    "EstadoTask",
    "ESTADOS_TERMINAIS",
    "Mensagem",
    "Artifact",
    "Status",
    "Task",
    "novo_id",
    "artifact_reserva",
]
