# Proposal

## Why

A fase 4 entregou a metade de fora do agente — o servidor A2A v1.0 (card, `SendMessage`, `GetTask`, máquina de estados da Task) — mas deixou a costura central do desafio em aberto: quando o servidor MCP responde `input_required`, o braço `Pausado` do controlador termina a Task em `TASK_STATE_FAILED` com uma mensagem placeholder. O resultado é que as sete verificações da ponte (PASS 27, 28, 29, 30, 32, 33 e 36) seguem vermelhas, e o desafio — cujo coração é exatamente a costura entre o `input_required` do MCP e a Task do A2A — não está completo. Esta fase fecha a ponte: pausar a Task em `TASK_STATE_INPUT_REQUIRED`, amarrar o `requestState` ao `taskId`, e retomar o `tools/call` com id JSON-RPC novo, sem tocar em nenhuma regra de negócio de sala.

## What Changes

- A Task passa a ter um estado **não-terminal** novo: `TASK_STATE_INPUT_REQUIRED`, alcançado quando o orquestrador devolve `Pausado` (o `InputRequiredResult` cru do MCP). O braço `Pausado` de `_traduzir` — hoje o ponto de extensão marcado na fase 4 — deixa de produzir `TASK_STATE_FAILED` e passa a produzir a pausa.
- A mensagem de status da pausa é **exatamente** `alternativas: <ids separados por virgula e espaco>`, na ordem do `enum` da elicitation do `inputRequests`. Sem prefixo, sem saudação — o avaliador compara duas pausas byte a byte (PASS 36).
- O `requestState` recebido do MCP fica **guardado no agente amarrado ao `taskId`** (um registro `taskId → Pausado`), e **não** aparece em nenhuma resposta A2A — nem card, nem artifact, nem mensagem, nem `history` (PASS 34, que segue verde).
- O `SendMessage` de continuação traz `taskId` e o texto `escolha=<valor>`, com três desfechos:
  - `escolha=<id>` **dentro do `enum`** → refaz o `tools/call` com **id JSON-RPC novo**, levando `inputResponses` com a **mesma chave** que veio no `inputRequests` e o `requestState` **ecoado sem modificação**; conclui a Task (`COMPLETED` + artifact `reserva`).
  - `escolha=<id>` **fora do `enum`** → mantém a Task em `TASK_STATE_INPUT_REQUIRED` e repete a linha `alternativas: ...`.
  - `escolha=recusar` → `action=decline` na elicitation → Task termina em `TASK_STATE_CANCELED`.
- O estado pausado é **por Task**: duas Tasks pausadas ao mesmo tempo concluem cada uma com a sua própria reserva, sem trocar de `requestState` (PASS 33).
- O agente **não** ganha regra de negócio: conflito, política, alternativas e o conteúdo do `requestState` continuam decisão/posse exclusiva do servidor MCP. O agente traduz protocolo e guarda estado nomeado.

## Capabilities

### New Capabilities

- `a-ponte`: a costura entre o `input_required` do MCP e a Task do A2A — pausa da Task em `TASK_STATE_INPUT_REQUIRED` com a linha `alternativas: <ids>` na ordem do `enum`, `requestState` amarrado ao `taskId` e nunca exposto, continuação via `escolha=<id>`/`escolha=recusar` (retry com id novo + `inputResponses` + `requestState` ecoado), estado pausado por Task, e ausência de regra de negócio de sala no agente.

### Modified Capabilities

Nenhuma. A ponte é uma camada **nova** por cima do `agente-servidor-a2a` (fase 4, ainda em voo e não arquivado): o `EstadoTask` ganha um valor, o braço `Pausado` muda de desfecho e o `_send_message` passa a tratar a continuação, mas nenhuma capacidade já publicada em `openspec/specs/` tem requisito alterado nesta fase.

## Impact

- **Código:** `agente/models/tarefa.py` ganha `EstadoTask.INPUT_REQUIRED` (e o estado fica **fora** de `ESTADOS_TERMINAIS`); `agente/controllers/a2a.py` troca o braço `Pausado` de `_traduzir`, adiciona o registro `taskId → Pausado` e implementa a continuação no ramo `task_id is not None` de `_send_message`. O orquestrador da fase 3 (`continuar`, que já refaz o `tools/call` com id novo e ecoa o `requestState`) é **reaproveitado sem alteração**; `servidor-mcp/`, `dados/`, `validador/` e `exemplos/` não são tocados.
- **Configuração:** nenhuma mudança — portas, paths e `MCP_URL` seguem como nas fases anteriores.
- **Dependências:** nenhuma nova.
- **Validador:** esta fase liga as sete verificações restantes da ponte — **PASS 27** (pausa), **PASS 28** (alternativas na ordem certa), **PASS 29** (escolha fora do `enum` mantém pausada), **PASS 30** (continuação conclui na sala escolhida), **PASS 32** (recusa → `CANCELED`), **PASS 33** (duas Tasks pausadas concluem cada uma com a sua) e **PASS 36** (determinismo da pausa). Total: **36/36**. PASS 01–26, 31, 34 e 35 permanecem verdes (fases 1–4).

## Não-objetivos

Fica fora desta fase, por decisão de escopo (o enunciado marca como fora de escopo ou já entregue em fases anteriores):

- Autenticação/autorização (OAuth, token, `securitySchemes` preenchido de verdade), streaming (`SendStreamingMessage`, SSE, push), refinamento de Task, `referenceTaskIds`, card estendido autenticado e assinatura JWS.
- Qualquer regra de negócio de sala no agente — o agente traduz protocolo, não domínio; conflito, política e alternativas seguem sendo do servidor MCP.
- Abrir, interpretar ou reconstruir o `requestState`: o agente guarda e ecoa, nunca lê (o conteúdo pode ser legível, o que não pode é ser tocado).
- Persistência de Task em disco: o registro de Tasks (e agora o de `Pausado`) continua em memória do processo, como as reservas.
- Alterar `dados/`, `validador/` ou `exemplos/` — permanecem intocados e somente leitura.
