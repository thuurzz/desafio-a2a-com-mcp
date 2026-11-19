# Fase 4 — Agente como servidor A2A

Branch: `fase-4-agente-a2a`. Spec: `openspec/changes/fase-4-agente-a2a/`.

## O que existe agora

O agente virou servidor A2A v1.0 na porta 7300, reaproveitando a profundidade MCP da fase 3:

- `agente/views/a2a.py` — app Starlette: `GET /.well-known/agent-card.json` e `POST /a2a`.
- `agente/servidor.py` — entrypoint (`A2A_PORT`, default 7300; `A2A_HOST`, default 127.0.0.1).
- `agente/controllers/a2a.py` — dispatcher JSON-RPC (`SendMessage`, `GetTask`) e máquina de estados.
- `agente/models/tarefa.py` — `EstadoTask`, `Task`, serialização do wire e artifact `reserva`.

Agent Card publicado conforme `exemplos/wire/07`:

```json
{"name":"Central de Salas","version":"1.0.0",
 "supportedInterfaces":[{"url":"http://127.0.0.1:7300/a2a","protocolBinding":"JSONRPC","protocolVersion":"1.0"}],
 "capabilities":{"streaming":false,"pushNotifications":false,"extendedAgentCard":false},
 "skills":[{"id":"reservar-sala", ...}]}
```

## Validador: 29/36

```
PASS 21 agent card responde 200 no well-known com JSON
PASS 22 o card declara a interface JSON-RPC com url e versao 1.0
PASS 23 o card declara a skill reservar-sala
PASS 24 SendMessage com sala livre conclui a Task
PASS 25 o artifact chama reserva e traz a versao da politica
PASS 26 GetTask devolve id, contextId e estado corrente
PASS 31 SendMessage em Task terminal e recusado
PASS 34 nenhuma resposta A2A carrega o requestState
PASS 35 sala inexistente termina a Task em FAILED com a mensagem da tool
```

Os 20 da fase 1–2 continuam verdes. Ficam para a fase 5 (a ponte): 27, 28, 29, 30, 32, 33, 36.

## O ponto de extensão da fase 5

Nesta fase, o braço `Pausado` termina em `TASK_STATE_FAILED` com a mensagem
`reserva em conflito: a pausa (TASK_STATE_INPUT_REQUIRED) sera implementada na fase 5`.
É determinístico e mantém 36 verde por acidente, mas o correto é a fase 5 trocar esse braço pela pausa
com `alternativas: ...` e o `requestState` amarrado ao `taskId`.

## Notas

- Starlette puro + uvicorn (não FastAPI): são as dependências que já vêm com o SDK `mcp`.
- Estado terminal é definitivo: COMPLETED/CANCELED/FAILED devolvem erro JSON-RPC em novo `SendMessage`.
- O card é derivado da mesma configuração de host/porta do servidor, então `A2A_PORT` não desalinha a URL.
