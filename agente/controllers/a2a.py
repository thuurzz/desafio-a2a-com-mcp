"""Controllers do agente: dispatcher JSON-RPC do servidor A2A (fase 4).

Este é o lado de fora do agente: o `ControladorA2A` atende `SendMessage` e `GetTask`
no binding JSON-RPC 2.0, mantém o registro de Tasks em memória (decisão 2 do design)
e traduz o `Resultado` da fase 3 para o estado terminal da Task (decisão 5).

Nenhuma regra de negócio de sala aqui: a profundidade é o orquestrador da fase 3
(`executar_pedido_async`), que já fala com o servidor MCP e propaga o `traceparent`.
O agente só traduz protocolo.

O braço `Pausado` da tradução é o **ponto de extensão da fase 5**: hoje ele termina a
Task em `TASK_STATE_FAILED` com uma mensagem determinística; a fase 5 troca esse mesmo
braço para produzir `TASK_STATE_INPUT_REQUIRED` e amarrar o `requestState` ao `taskId`.
"""

from __future__ import annotations

from typing import Any

from agente.controllers.orquestrador import executar_pedido as _executar_pedido_async
from agente.models.pedido import Completado, Falhou, Pausado, Resultado
from agente.models.tarefa import (
    Artifact,
    EstadoTask,
    Mensagem,
    Status,
    Task,
    artifact_reserva,
    novo_id,
)

CODIGO_TASK_TERMINAL = -32000
CODIGO_TASK_INEXISTENTE = -32001
CODIGO_METODO_DESCONHECIDO = -32601

# Mensagem determinística do braço `Pausado` nesta fase. A fase 5 substitui este
# desfecho pela pausa `TASK_STATE_INPUT_REQUIRED` (com `alternativas: <ids>`).
MENSAGEM_PAUSA_PLACEHOLDER = (
    "reserva em conflito: a pausa (TASK_STATE_INPUT_REQUIRED) sera "
    "implementada na fase 5"
)


class ErroJsonRpc(Exception):
    """Erro JSON-RPC determinístico, devolvido no campo `error` do envelope."""

    def __init__(self, codigo: int, mensagem: str) -> None:
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(mensagem)


def _extrair_texto(mensagem: dict) -> str:
    """Concatena o texto das `parts[*].text` da mensagem do usuário."""
    partes = mensagem.get("parts") or []
    return " ".join(p.get("text", "") for p in partes if isinstance(p, dict))


def _mensagem_usuario(mensagem: dict) -> Mensagem:
    """Reconstrói a mensagem do usuário no histórico, preservando id/role/parts."""
    return Mensagem(
        messageId=mensagem.get("messageId") or novo_id("msg"),
        role=mensagem.get("role") or "ROLE_USER",
        parts=mensagem.get("parts") or [],
    )


def _mensagem_agente(texto: str, tarefa: Task) -> Mensagem:
    """Monta a mensagem do agente (status + histórico) com `taskId`/`contextId`."""
    return Mensagem(
        messageId=novo_id("msg"),
        role="ROLE_AGENT",
        parts=[{"text": texto}],
        taskId=tarefa.id,
        contextId=tarefa.contextId,
    )


def _traduzir(resultado: Resultado) -> tuple[EstadoTask, str, Artifact | None]:
    """Traduz o `Resultado` da fase 3 para `(estado, mensagem, artifact|None)`.

    Decisão 5 do design:

    - `Completado(reservado=True)` → `COMPLETED` + artifact `reserva`;
    - `Completado(reservado=False)` → `CANCELED` (texto da recusa);
    - `Falhou(mensagem)` → `FAILED` (a mensagem exata da tool);
    - `Pausado(...)` → `FAILED` com mensagem determinística — **ponto de extensão
      da fase 5**, que troca este braço por `TASK_STATE_INPUT_REQUIRED`.
    """
    if isinstance(resultado, Completado):
        if resultado.reservado:
            texto = f"Reserva {resultado.reserva} confirmada na {resultado.sala}."
            artifact = Artifact(
                artifactId=novo_id("art"),
                name="reserva",
                parts=[
                    {
                        "text": artifact_reserva(
                            resultado.reserva,
                            resultado.sala,
                            resultado.inicio,
                            resultado.fim,
                            resultado.responsavel,
                            resultado.politica,
                        )
                    }
                ],
            )
            return EstadoTask.CONCLUIDA, texto, artifact
        texto = resultado.motivo or "Reserva recusada."
        return EstadoTask.CANCELADA, texto, None

    if isinstance(resultado, Falhou):
        return EstadoTask.FALHOU, resultado.mensagem, None

    if isinstance(resultado, Pausado):
        # ---- PONTO DE EXTENSÃO DA FASE 5 ----
        # Aqui a fase 5 intercepta o `Pausado`: monta `alternativas: <ids>` a partir
        # do `enum` da elicitation e amarra o `requestState` (já carregado em
        # `Pausado.request_state`) ao id da Task, produzindo `TASK_STATE_INPUT_REQUIRED`.
        return EstadoTask.FALHOU, MENSAGEM_PAUSA_PLACEHOLDER, None

    raise TypeError(f"Resultado inesperado: {type(resultado).__name__}")


class ControladorA2A:
    """Dispatcher JSON-RPC: registro de Tasks em memória + máquina de estados.

    O registro (`dict[str, Task]`) vive em memória do processo; um restart zera tudo,
    coerente com a persistência em memória das reservas. O `requestState` não vive aqui
    — na fase 5 ele será amarrado à Task (ver o braço `Pausado` de `_traduzir`).
    """

    def __init__(self) -> None:
        self._tarefas: dict[str, Task] = {}

    async def tratar(
        self, metodo: str | None, id_req: Any, params: dict, traceparent: str | None
    ) -> dict:
        """Despacha um request JSON-RPC e devolve o envelope completo.

        O `id` do request é ecoado byte a byte (string ou número), no `result` ou no
        `error`. `metodo`/`id`/`params` vêm crus da rota; a validação é mínima e
        determinística.
        """
        try:
            if metodo == "SendMessage":
                tarefa = await self._send_message(params or {}, traceparent)
                return {
                    "jsonrpc": "2.0",
                    "id": id_req,
                    "result": {"task": tarefa.para_dict()},
                }
            if metodo == "GetTask":
                tarefa = self._get_task(params or {})
                return {
                    "jsonrpc": "2.0",
                    "id": id_req,
                    "result": {"task": tarefa.para_dict()},
                }
            raise ErroJsonRpc(
                CODIGO_METODO_DESCONHECIDO, f"metodo desconhecido: {metodo}"
            )
        except ErroJsonRpc as erro:
            return {
                "jsonrpc": "2.0",
                "id": id_req,
                "error": {"code": erro.codigo, "message": erro.mensagem},
            }

    async def _send_message(self, params: dict, traceparent: str | None) -> Task:
        mensagem = params.get("message") or {}
        task_id = mensagem.get("taskId")
        texto = _extrair_texto(mensagem)

        if task_id is not None:
            tarefa = self._tarefas.get(task_id)
            if tarefa is None:
                raise ErroJsonRpc(
                    CODIGO_TASK_INEXISTENTE, f"Task {task_id} nao encontrada"
                )
            if tarefa.eh_terminal():
                # Terminalidade definitiva: nunca volta a WORKING (decisão 6).
                raise ErroJsonRpc(
                    CODIGO_TASK_TERMINAL,
                    f"Task {task_id} is in terminal state {tarefa.status.estado.value}",
                )
            # Fase 5: continuação de uma Task pausada. Nesta fase nenhuma Task fica
            # observável num estado não-terminal (execução síncrona), então este ramo
            # não é alcançado; a fase 5 implementa a retomada aqui.
            raise ErroJsonRpc(
                CODIGO_TASK_TERMINAL,
                f"continuacao da Task {task_id} e da fase 5 (nao implementada)",
            )

        return await self._abrir_e_executar(mensagem, texto, traceparent)

    async def _abrir_e_executar(
        self, mensagem: dict, texto: str, traceparent: str | None
    ) -> Task:
        # Abertura: SUBMITTED → registra a mensagem do usuário → WORKING → executa.
        tarefa = Task(
            id=novo_id("task"),
            contextId=novo_id("ctx"),
            status=Status(EstadoTask.SUBMETIDA, None),
        )
        self._tarefas[tarefa.id] = tarefa
        tarefa.history.append(_mensagem_usuario(mensagem))
        tarefa.status = Status(EstadoTask.TRABALHANDO, None)

        try:
            resultado = await _executar_pedido_async(texto, traceparent)
        except Exception as exc:  # malformado, MCP fora, etc. → FAILED determinístico
            resultado = Falhou(mensagem=str(exc))

        estado, texto_status, artifact = _traduzir(resultado)
        agente = _mensagem_agente(texto_status, tarefa)
        tarefa.status = Status(estado, agente)
        tarefa.history.append(agente)
        if artifact is not None:
            tarefa.artifacts.append(artifact)
        return tarefa

    def _get_task(self, params: dict) -> Task:
        task_id = params.get("id")
        tarefa = self._tarefas.get(task_id)
        if tarefa is None:
            raise ErroJsonRpc(
                CODIGO_TASK_INEXISTENTE, f"Task {task_id} nao encontrada"
            )
        return tarefa


__all__ = ["ControladorA2A", "ErroJsonRpc", "MENSAGEM_PAUSA_PLACEHOLDER"]
