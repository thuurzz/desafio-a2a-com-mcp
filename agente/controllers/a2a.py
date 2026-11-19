"""Controllers do agente: dispatcher JSON-RPC do servidor A2A (fase 4).

Este é o lado de fora do agente: o `ControladorA2A` atende `SendMessage` e `GetTask`
no binding JSON-RPC 2.0, mantém o registro de Tasks em memória (decisão 2 do design)
e traduz o `Resultado` da fase 3 para o estado terminal da Task (decisão 5).

Nenhuma regra de negócio de sala aqui: a profundidade é o orquestrador da fase 3
(`executar_pedido_async` / `continuar_async`), que já fala com o servidor MCP e
propaga o `traceparent`. O agente só traduz protocolo.

O braço `Pausado` da tradução (fase 5) produz a pausa `TASK_STATE_INPUT_REQUIRED`
com a linha `alternativas: <ids>`, e amarra o `requestState` ao `taskId` no registro
`self._pausas` (que nunca é serializado). A continuação vem por `escolha=<valor>`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agente.controllers.orquestrador import (
    continuar as _continuar_async,
    executar_pedido as _executar_pedido_async,
)
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

# Sentinela de recusa na continuação `escolha=recusar` (espelha `OPCAO_RECUSAR` do
# orquestrador, que a traduz em `action=decline` no retry).
ESCOLHA_RECUSAR = "recusar"

# Falha de transporte do MCP: mensagem determinística (sem detalhe de biblioteca, que
# variaria entre versões e quebraria a regra de resposta estável da Task).
MENSAGEM_MCP_INDISPONIVEL = (
    "MCP indisponivel: nao foi possivel concluir a reserva (falha de conexao com o servidor MCP)"
)


def _absorver_cancelamento() -> None:
    """Consome o cancelamento já entregue, para o handler chegar ao fim normalmente.

    `Task.uncancel()` (3.11+) decrementa o contador que o `cancel()` armou. Sem isso
    o próximo `await` do handler voltaria a levantar `CancelledError`.
    """
    tarefa = asyncio.current_task()
    if tarefa is not None and hasattr(tarefa, "uncancel"):
        while tarefa.cancelling():
            tarefa.uncancel()


async def _falar_com_mcp(espera: Any) -> Resultado:
    """Executa a chamada ao MCP traduzindo qualquer falha de transporte em `Falhou`.

    Por que este invólucro existe: o SDK do MCP roda o POST dentro de um task group do
    anyio. Quando a conexão com o servidor falha, o grupo cancela a task que esperava a
    resposta e o que escapa no ponto do `await` é `CancelledError` — que herda de
    `BaseException`, então um `except Exception` não pega. Sem esta tradução o handler
    morre e o cliente A2A recebe **HTTP 500**, em vez de uma Task em `TASK_STATE_FAILED`.

    Absorver o cancelamento é seguro neste ponto porque o código que segue é síncrono:
    nada mais é aguardado até o fim do handler.
    """
    try:
        return await espera
    except asyncio.CancelledError:
        _absorver_cancelamento()
        return Falhou(mensagem=MENSAGEM_MCP_INDISPONIVEL)
    except Exception as exc:  # malformado, MCP fora por outra via, etc.
        return Falhou(mensagem=str(exc))


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


def _schema_da_escolha(pausado: Pausado) -> dict[str, Any]:
    """Devolve o `requestedSchema` cru da elicitation do `Pausado` (ou `{}`).

    Em runtime o `input_requests[chave]` é um `ElicitRequest` do SDK (pydantic), cujo
    schema vive em `.params.requested_schema`; em teste/verificação ele chega como um
    `dict` com a chave `requestedSchema`. Esta função cobre os dois, sem abrir o
    `requestState` (que permanece opaco).
    """
    chave = next(iter(pausado.input_requests), None)
    if chave is None:
        return {}
    solicitacao = pausado.input_requests[chave]
    if isinstance(solicitacao, dict):
        return (solicitacao.get("params") or {}).get("requestedSchema") or {}
    params = getattr(solicitacao, "params", None)
    schema = getattr(params, "requested_schema", None)
    return schema or {}


def alternativas_de(pausado: Pausado) -> list[str]:
    """Lista de ids de sala alternativos, na ordem do `enum` da elicitation.

    A única introspecção que o agente faz sobre o `Pausado` (decisão 3 do design):
    lê o `enum` visível de `properties.sala`, com fallback para `const` (uma única
    alternativa). Nunca reordena, nunca toca no `requestState`.
    """
    schema = _schema_da_escolha(pausado)
    sala = (schema.get("properties") or {}).get("sala") or {}
    enum = sala.get("enum")
    if isinstance(enum, list):
        return [str(valor) for valor in enum]
    if "const" in sala:
        return [str(sala["const"])]
    return []


def _escolha_de(texto: str) -> str | None:
    """Extrai o `<valor>` de `escolha=<valor>`; `None` quando o prefixo não casa."""
    if not texto.startswith("escolha="):
        return None
    return texto[len("escolha="):]


def _traduzir(resultado: Resultado) -> tuple[EstadoTask, str, Artifact | None]:
    """Traduz o `Resultado` da fase 3 para `(estado, mensagem, artifact|None)`.

    Decisão 5 do design:

    - `Completado(reservado=True)` → `COMPLETED` + artifact `reserva`;
    - `Completado(reservado=False)` → `CANCELED` (texto da recusa);
    - `Falhou(mensagem)` → `FAILED` (a mensagem exata da tool);
    - `Pausado(...)` → `INPUT_REQUIRED` + a linha `alternativas: <ids>` (na ordem do
      `enum`), sem artifact (decisão 4 do design).
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
        alternativas = alternativas_de(resultado)
        return EstadoTask.INPUT_REQUIRED, "alternativas: " + ", ".join(alternativas), None

    raise TypeError(f"Resultado inesperado: {type(resultado).__name__}")


class ControladorA2A:
    """Dispatcher JSON-RPC: registro de Tasks em memória + máquina de estados.

    O registro (`dict[str, Task]`) vive em memória do processo; um restart zera tudo,
    coerente com a persistência em memória das reservas. O `requestState` vive só em
    `_pausas` (um `dict[str, Pausado]` indexado por `taskId`), e nunca é serializado
    em nenhuma resposta A2A (decisão 2 do design).
    """

    def __init__(self) -> None:
        self._tarefas: dict[str, Task] = {}
        self._pausas: dict[str, Pausado] = {}

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
            if tarefa.status.estado != EstadoTask.INPUT_REQUIRED:
                # Defensivo: a execução é síncrona, então o único estado não-terminal
                # observável para uma continuação é a pausa.
                raise ErroJsonRpc(
                    CODIGO_TASK_TERMINAL,
                    f"Task {task_id} is in terminal state {tarefa.status.estado.value}",
                )
            return await self._continuar(tarefa, mensagem, texto)

        return await self._abrir_e_executar(mensagem, texto, traceparent)

    async def _continuar(self, tarefa: Task, mensagem: dict, texto: str) -> Task:
        """Retoma uma Task pausada (`INPUT_REQUIRED`) a partir de `escolha=<valor>`.

        Decisão 5 do design: o `requestState` vem do `self._pausas[task_id]` daquela
        Task (nunca de um global). `escolha=<id no enum>` chama `continuar` (retry com
        id novo); `escolha=recusar` chama `continuar(..., "recusar")` (→ `decline`).
        Qualquer outro texto, ou um id fora do `enum`, mantém a pausa e repete a linha
        de alternativas **sem chamar o MCP** (PASS 29).
        """
        pausa = self._pausas.get(tarefa.id)
        if pausa is None:
            raise ErroJsonRpc(
                CODIGO_TASK_TERMINAL,
                f"Task {tarefa.id} pausada sem registro de requestState",
            )

        alternativas = alternativas_de(pausa)
        linha = "alternativas: " + ", ".join(alternativas)
        valor = _escolha_de(texto)

        if valor is None or (valor not in alternativas and valor != ESCOLHA_RECUSAR):
            # Escolha ausente ou fora do `enum`: mantém a pausa e repete a linha.
            agente = _mensagem_agente(linha, tarefa)
            tarefa.history.append(_mensagem_usuario(mensagem))
            tarefa.history.append(agente)
            tarefa.status = Status(EstadoTask.INPUT_REQUIRED, agente)
            return tarefa

        resultado = await _falar_com_mcp(_continuar_async(pausa, valor))
        estado, texto_status, artifact = _traduzir(resultado)
        agente = _mensagem_agente(texto_status, tarefa)
        tarefa.history.append(_mensagem_usuario(mensagem))
        tarefa.history.append(agente)
        tarefa.status = Status(estado, agente)
        if artifact is not None:
            tarefa.artifacts.append(artifact)
        return tarefa

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

        resultado = await _falar_com_mcp(_executar_pedido_async(texto, traceparent))

        # Amarra o `requestState` (dentro do `Pausado`) ao id da Task ANTES de montar
        # o status — o registro é por Task, nunca global (decisão 2 do design).
        if isinstance(resultado, Pausado):
            self._pausas[tarefa.id] = resultado

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


__all__ = ["ControladorA2A", "ErroJsonRpc", "alternativas_de"]
