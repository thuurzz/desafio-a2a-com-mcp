# Proposal

## Why

A fase 1 entregou o servidor MCP base (transporte, tools, resource, validações de política), mas `reservar_sala` ainda só cobre o caminho feliz e o conflito sem alternativas. No enunciado, o conflito com alternativas não é um erro: é o ponto de entrada do ciclo MRTR (Model-Response-Task-Response), que resolve a ausência de sessão devolvendo ao cliente um `input_required` com elicitation em form mode e um `requestState` opaco e protegido por integridade. Sem esse ciclo, o servidor não consegue pedir a escolha entre salas alternativas nem concluir a reserva escolhida, e o validador trava nas verificações 13 a 19.

## What Changes

- `reservar_sala` deixa de devolver `isError` para conflito **com alternativas** e passa a devolver `resultType="input_required"`, com `inputRequests` de **uma única entrada** (`elicitation/create`, `mode=form`), `requestedSchema` plano restringindo a propriedade `sala` por `enum` às alternativas na ordem já implementada, e `requestState` presente.
- O `requestState` passa a ser selado pelo `RequestStateBoundary` do SDK com `RequestStateSecurity(keys=[REQUEST_STATE_SECRET], ttl=900)`. A chave vem **sempre** de variável de ambiente (o repositório é público); se faltar ou tiver menos de 32 bytes, o processo **falha na subida** com mensagem clara.
- Cliente sem capability de elicitation em form mode pedindo reserva em conflito recebe `-32021` com `data.requiredCapabilities` e HTTP `400`.
- O retry lê `inputResponses` e `requestState`, reconstrói o pedido a partir do estado selado (não dos argumentos reenviados), conclui a reserva e devolve `resultType="complete"` com o `structuredContent` de sempre.
- `action` igual a `decline` ou `cancel` conclui **sem** reservar, sem `isError`, com `reservado=false` e `motivo`.
- `requestState` adulterado, expirado ou reapresentado com outros argumentos é rejeitado com `-32602` (o SDK já rejeita; o handler não engole o erro).
- Sem nenhuma alternativa, o comportamento **não muda**: continua `isError` com `Sem alternativas disponiveis no intervalo`, sem elicitation.
- A regra de negócio (conflito, política, cálculo de alternativas) continua em `controllers/salas.py`; o handler de `views/` apenas traduz protocolo (devolve `InputRequiredResult` ou trata o retry).
- Reservas continuam em memória; apenas o `requestState` precisa sobreviver a restart — e ele sobrevive porque viaja selado no token, não no processo.

## Não-objetivos

Fica fora desta fase, por decisão de escopo (e por estar fora de escopo ou em fase posterior no enunciado):

- O agente A2A inteiro: host MCP por dentro (`tools/list` em runtime, leitura do resource, headers `Mcp-Method`/`Mcp-Name`, propagação de `traceparent`), servidor A2A por fora (Agent Card, `SendMessage`, `GetTask`, máquina de estados da Task) e a ponte entre `input_required` e `TASK_STATE_INPUT_REQUIRED`. Esta fase é só o lado servidor MCP do ciclo MRTR.
- Autenticação e autorização (OAuth, token, `securitySchemes` real), streaming/SSE/push, prompts, subscriptions, progress, refinamento de Task e `referenceTaskIds`.
- Container, compose, deploy, gateway, spans/atributos de OpenTelemetry e interface gráfica.
- Persistência em disco das reservas criadas (memória do processo basta) e qualquer tratamento de concorrência de escrita.
- Alterar `dados/`, `validador/` ou `exemplos/` — permanecem intocados e somente leitura.
- Alterar as mensagens de erro já fechadas na fase 1 e as verificações 01–12 e 20, que permanecem com o comportamento atual.

## Capabilities

### New Capabilities

Nenhuma: o ciclo MRTR estende o comportamento de `servidor-mcp`, capability já introduzida na fase 1.

### Modified Capabilities

- `servidor-mcp`: `reservar_sala` ganha o ciclo completo de MRTR — `input_required` com elicitation form mode e `requestState` selado, rejeição `-32021` para cliente sem capability, retry que reconstrói o pedido a partir do estado selado, recusa `decline`/`cancel` sem reservar e rejeição `-32602` para `requestState` inválido. A regra de alternativas continua vivendo em `controllers/salas.py` e o conflito sem alternativa continua devolvendo `isError`.

## Impact

- **Código novo/alterado:** `servidor-mcp/` — novo middleware `RequestStateBoundary` no `Server.middleware`, configuração de `RequestStateSecurity` com chave de env, novo caminho em `views/` para devolver `InputRequiredResult` e tratar o retry, e o cálculo de alternativas em `controllers/salas.py` (já fechado na regra do enunciado). Nenhum outro diretório de aplicação é tocado.
- **Configuração:** nova variável de ambiente `REQUEST_STATE_SECRET` (obrigatória, ≥ 32 bytes); processo falha na subida se ausente ou curta. Documentada no README como gerar, nunca o valor usado.
- **Dependências:** nenhuma nova. `RequestStateBoundary`/`RequestStateSecurity` vêm do próprio SDK `mcp>=2.3,<3`.
- **Dados:** leitura de `dados/salas.json` e `dados/reservas.json`; nenhuma escrita nesses arquivos. Reservas novas seguem em memória.
- **Validador:** esta fase habilita **PASS 13–19** (conflito → `input_required`; elicitation form com `enum` na ordem; `-32021` sem capability; retry concluindo; `requestState` adulterado → `-32602`; argumentos adulterados não tomam efeito; recusa sem reservar). **PASS 01–12** e **PASS 20** permanecem verdes (fase 1). Ficam **pendentes** **PASS 21–36** (dependem do agente A2A e da ponte, fase 3).
