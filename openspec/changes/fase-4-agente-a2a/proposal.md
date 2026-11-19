# Proposal

## Why

A fase 3 entregou a metade de dentro do agente: um processo separado que é **host MCP de verdade** — descobre as tools, lê o resource da política e percorre o ciclo MRTR como cliente — exposto como biblioteca interna (`executar_pedido`/`continuar`, resultado tipado `completado`/`pausado`/`falhou`). O que falta é a metade de fora: sem servidor A2A, a porta 7300 responde `Connection refused` e o validador trava logo na verificação 21, deixando todo o bloco A2A (21–36) sem por onde rodar. Esta fase põe o agente **de frente para o mundo** como servidor A2A v1.0, reaproveitando o orquestrador da fase 3 como profundidade, e deixa a ponte (pausa/retomada) como único fio solto para a fase 5.

## What Changes

- Novo servidor A2A v1.0 no **mesmo processo** do agente, em ASGI (Starlette + uvicorn, já disponíveis como dependência do SDK — não há `fastapi` no ambiente), escutando em `http://0.0.0.0:7300` (porta parametrizável por env, default `7300`).
- `GET /.well-known/agent-card.json` devolvendo o Agent Card na forma exata da v1.0 (`supportedInterfaces` com `protocolBinding: "JSONRPC"`, `url` do endpoint e `protocolVersion: "1.0"`, `capabilities`, e a skill `id: reservar-sala`), espelhando `exemplos/wire/07-a2a-agent-card.json`.
- `POST /a2a` em JSON-RPC 2.0 com dois métodos: `SendMessage` e `GetTask` (id do request ecoado na resposta).
- `SendMessage` sem `taskId` abre uma Task nova com `id` e `contextId` próprios; a Task transita por `TASK_STATE_SUBMITTED` → `TASK_STATE_WORKING` e chega a um estado terminal (`COMPLETED`, `FAILED` ou `CANCELED`).
- A Task mantém `history` (a mensagem do usuário + as mensagens do agente) e, em sucesso, um artifact `name: "reserva"` cujo conteúdo é o JSON da reserva (`reserva`, `sala`, `inicio`, `fim`, `responsavel`, `politica` — a versão lida do resource).
- `GetTask` devolve `id`, `contextId`, estado corrente, `history` e `artifacts` da Task.
- Estado terminal é definitivo: `SendMessage` referenciando uma Task em `COMPLETED`/`FAILED`/`CANCELED` é recusado com **erro JSON-RPC** (não volta a `WORKING`).
- `isError` da tool (ex.: sala inexistente) termina a Task em `TASK_STATE_FAILED` com a **mensagem exata** da tool no histórico.
- O `traceparent` do header A2A é propagado ao orquestrador (que já o leva ao `_meta` do MCP) — o mesmo trace-id chega ao servidor MCP.
- O agente **não** implementa regra de negócio de sala: conflito, política e alternativas continuam decisão exclusiva do servidor MCP.

## Não-objetivos

Fica fora desta fase, por decisão de escopo (fase 5, ou fora de escopo no enunciado):

- **A ponte (fase 5):** a pausa `TASK_STATE_INPUT_REQUIRED`, a linha `alternativas: <ids separados por virgula e espaco>`, o `escolha=<id>`/`escolha=recusar`, o `requestState` amarrado ao `taskId` e o estado pausado por Task. Nesta fase, um conflito (o `input_required` do MCP) termina a Task em `TASK_STATE_FAILED`; a fase 5 troca esse desfecho pela pausa. O design já marca o ponto de extensão onde a fase 5 intercepta o resultado `pausado`.
- Autenticação/autorização (OAuth, token, `securitySchemes` preenchido de verdade), streaming (`SendStreamingMessage`, SSE, push), refinamento de Task, `referenceTaskIds`, card estendido autenticado e assinatura JWS.
- Container, compose, deploy, gateway, spans/atributos de OpenTelemetry e interface gráfica.
- Qualquer regra de negócio de sala no agente — o agente traduz protocolo, não domínio.
- Alterar `dados/`, `validador/` ou `exemplos/` — permanecem intocados e somente leitura.

## Capabilities

### New Capabilities

- `agente-servidor-a2a`: o agente atuando como servidor A2A v1.0 — publicação do Agent Card no well-known URI, atendimento de `SendMessage` e `GetTask` em JSON-RPC 2.0 sobre `/a2a`, máquina de estados da Task (`SUBMITTED` → `WORKING` → terminal), artifact `reserva`, terminalidade definitiva (recusa de `SendMessage` em Task terminal) e tradução de `isError` da tool para `TASK_STATE_FAILED` com a mensagem exata — tudo reaproveitando o orquestrador MCP da fase 3 como profundidade.

### Modified Capabilities

Nenhuma. O `agente-host-mcp` (fase 3) não muda de comportamento nesta fase: o servidor A2A é uma camada **nova** por cima da biblioteca interna, que continua consumindo o servidor MCP por HTTP como um cliente MCP de verdade.

## Impact

- **Código novo:** `agente/` ganha a superfície A2A — `models/tarefa.py` (modelo da Task, estados, mensagens e artifact), `controllers/a2a.py` (dispatcher JSON-RPC que orquestra a Task chamando o orquestrador da fase 3) e `views/a2a.py` (app Starlette com as rotas do card e do `/a2a`). Novo entrypoint que sobe o uvicorn na porta 7300. Nenhum arquivo de `servidor-mcp/`, `dados/`, `validador/` ou `exemplos/` é tocado; a biblioteca da fase 3 (`controllers/orquestrador.py`, `views/cliente.py`, `models/pedido.py`) é reaproveitada sem alteração.
- **Configuração:** porta do servidor A2A parametrizável por env (default `7300`); URL do MCP já parametrizável (`MCP_URL`, default `http://127.0.0.1:7301/mcp`).
- **Dependências:** nenhuma nova — `mcp>=2.3,<3` já traz `starlette` e `uvicorn` (sem `fastapi` no ambiente). Sem dependência de provedor de LLM.
- **Validador:** esta fase liga as verificações do Agent Card (**PASS 21, 22, 23**), do caminho de sucesso (`SendMessage` com sala livre → `COMPLETED` + artifact → **PASS 24, 25**) e do `GetTask` (**PASS 26**), a recusa de Task terminal (**PASS 31**) e a falha de sala inexistente (**PASS 35**). Total: 28/36. Ficam pendentes para a fase 5 as verificações da ponte (**PASS 27, 28, 29, 30, 32, 33, 34, 36**), que dependem da pausa `TASK_STATE_INPUT_REQUIRED`. PASS 01–20 permanecem verdes (fases 1 e 2).
