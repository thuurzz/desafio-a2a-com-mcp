# Proposal

## Why

A fase 2 fechou todo o lado servidor do desafio (PASS 01–20; 20/36), mas o enunciado exige dois processos: o servidor MCP e o agente que o consome. Hoje `agente/` é um `.gitkeep` — sem ele, o validador trava em `Connection refused` na porta 7300 e nenhuma das verificações A2A (21–36) tem por onde rodar. Esta fase constrói a metade de dentro do agente: um processo separado que é **host MCP de verdade** — descobre as tools em runtime, lê o resource da política e percorre o ciclo MRTR como cliente — deixando pronta a biblioteca interna que as fases 4 (servidor A2A) e 5 (a ponte) vão plugar.

## What Changes

- Novo projeto Python em `agente/` (`pyproject.toml` com `mcp>=2.3,<3`, layout `models/`, `controllers/`, `views/`), processo **separado** do servidor MCP, falando com ele por HTTP em `http://127.0.0.1:7301/mcp` (parametrizável por env).
- Descoberta das tools por `tools/list` em runtime, **antes** da primeira chamada de tool — nada de catálogo hardcoded.
- Leitura do resource `politica://uso` e extração da versão da primeira linha (`versao: <valor>`), que vira o campo `politica` do resultado de uma reserva concluída.
- Todo request MCP emitido carrega `_meta` completo: `io.modelcontextprotocol/protocolVersion`, `io.modelcontextprotocol/clientCapabilities` com `{"elicitation": {"form": {}}}`, `clientInfo`, e o `traceparent` da chamada de entrada (trace-id preservado, span-id pode ser novo).
- Headers do transporte espelhando o corpo: `MCP-Protocol-Version`, `Mcp-Method` e, em `tools/call` e `resources/read`, `Mcp-Name`.
- Interpretação do pedido fixo `reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>` por regra, **sem LLM**, chamando `reservar_sala` e produzindo um resultado tipado: reserva criada (com `politica`), pausa (`input_required` cru, com `inputRequests` e `requestState` guardados sem interpretar) e falha (mensagem exata da tool).
- Uma biblioteca interna (`agente/controllers/`) expondo `executar_pedido(texto, traceparent)` — devolvendo um objeto de resultado tipado (`completado`/`pausado`/`falhou`) — e `continuar(task, escolha)` — refazendo o `tools/call` com id novo + `inputResponses` + `requestState` ecoado. É essa biblioteca que a fase 4 pluga no servidor A2A.
- O `requestState` é **opaco** para o agente: guardar e devolver, nunca abrir, interpretar nem reconstruir.

## Não-objetivos

Fica fora desta fase, por decisão de escopo (e por estar em fase posterior ou fora de escopo no enunciado):

- O agente como servidor A2A (fase 4): Agent Card em `/.well-known/agent-card.json`, `SendMessage`, `GetTask` e a máquina de estados da Task (`SUBMITTED` → `WORKING` → terminal).
- A ponte (fase 5): a pausa da Task em `TASK_STATE_INPUT_REQUIRED`, a linha `alternativas: `, o `requestState` amarrado ao `taskId`, o retry com id JSON-RPC novo, a recusa `CANCELED` e o isolamento de estado por Task.
- Autenticação/autorização (OAuth, token, `securitySchemes`), streaming/SSE/push, prompts, subscriptions, progress, refinamento de Task e `referenceTaskIds`.
- Container, compose, deploy, gateway, spans/atributos de OpenTelemetry e interface gráfica.
- Qualquer regra de negócio de sala no agente: conflito, política e alternativas seguem decisão exclusiva do servidor MCP — o agente traduz protocolo, não domínio.
- Alterar `dados/`, `validador/` ou `exemplos/` — permanecem intocados e somente leitura.

## Capabilities

### New Capabilities

- `agente-host-mcp`: o agente atuando como host MCP — descoberta de tools em runtime, leitura do resource com extração da versão da política, emissão de requests MCP com `_meta` completo e headers espelhados, propagação do `traceparent`, interpretação por regra do pedido fixo e orquestração do ciclo de `reservar_sala` (reserva criada, pausa `input_required`, falha), exposta como biblioteca interna com resultado tipado e `requestState` opaco.

### Modified Capabilities

Nenhuma. O `servidor-mcp` (fases 1 e 2) não muda nesta fase; o agente apenas o consome por HTTP como um cliente MCP de verdade.

## Impact

- **Código novo:** `agente/` — novo `pyproject.toml` (`mcp>=2.3,<3`), `models/` (schemas e o tipo de resultado `completado`/`pausado`/`falhou`), `controllers/` (interpretação do pedido + orquestração `executar_pedido`/`continuar`) e `views/` (cliente MCP Streamable HTTP que serializa o `_meta` e espelha os headers). Nenhum arquivo de `servidor-mcp/`, `dados/`, `validador/` ou `exemplos/` é tocado.
- **Configuração:** URL do servidor MCP (`http://127.0.0.1:7301/mcp`) parametrizável por env, com esse valor como default.
- **Dependências:** `mcp>=2.3,<3` (já no ambiente; o cliente usa os tipos de wire do próprio SDK). Sem dependência de provedor de LLM.
- **Validador:** esta fase **não liga nenhum PASS novo por si só** — PASS 21–36 seguem pendentes, pois dependem do servidor A2A das fases 4 e 5. O gate observável desta fase é o **stderr do servidor MCP**: o `tools/list` aparecendo **antes** do primeiro `tools/call` do agente e o `traceparent` com o mesmo trace-id da chamada de entrada (itens do README §3 e dos critérios "Agente como host MCP"). PASS 01–20 permanecem verdes (fase 2).
