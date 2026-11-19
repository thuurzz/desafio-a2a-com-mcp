# Spec Delta

## Purpose

Define o contrato observável do agente atuando como host MCP: descoberta de tools em runtime, leitura do resource da política com extração da versão, requests MCP com metadados completos e headers espelhados, propagação do `traceparent`, interpretação determinística do pedido de reserva sem LLM e `requestState` tratado como opaco.

## ADDED Requirements

### Requirement: Descoberta de tools em runtime

O agente SHALL descobrir as tools do servidor MCP por uma chamada `tools/list` antes da primeira chamada de tool, e MUST NOT carregar um catálogo fixo de tools no código.

#### Scenario: tools/list precede o primeiro tools/call

- **WHEN** o agente é acionado para interpretar um pedido de reserva
- **THEN** o servidor MCP registra no stderr um `tools/list` anterior ao primeiro `tools/call` do agente
- **AND** o agente não consulta nenhuma lista de tools hardcoded

### Requirement: Leitura do resource e extração da versão

O agente SHALL ler o resource `politica://uso` e extrair a versão declarada na primeira linha (a linha `versao: <valor>`). O valor extraído SHALL ser usado como o campo `politica` do resultado de uma reserva concluída.

#### Scenario: versão da política é lida do resource

- **WHEN** o agente lê `politica://uso`, cujo conteúdo começa com `versao: 2026-11-01`
- **THEN** o campo `politica` do resultado de uma reserva concluída é `2026-11-01`

### Requirement: Metadados completos em todo request MCP

Todo request MCP emitido pelo agente SHALL carregar `_meta` com `io.modelcontextprotocol/protocolVersion` igual a `2026-07-28`, `io.modelcontextprotocol/clientCapabilities` com `{"elicitation": {"form": {}}}`, `io.modelcontextprotocol/clientInfo` com `name` e `version`, e, quando a chamada de entrada trouxer `traceparent`, o `traceparent` correspondente.

#### Scenario: request MCP com _meta completo

- **WHEN** o agente emite qualquer request MCP (`tools/list`, `resources/read` ou `tools/call`)
- **THEN** o `_meta` contém `protocolVersion`, `clientCapabilities` com elicitation em form mode e `clientInfo`

#### Scenario: traceparent propagado com o mesmo trace-id

- **WHEN** a chamada de entrada traz um `traceparent` com um trace-id
- **THEN** todos os requests MCP daquela execução carregam um `traceparent` com o mesmo trace-id
- **AND** o span-id pode ser novo

### Requirement: Headers do transporte espelhando o corpo

O agente SHALL emitir os headers `MCP-Protocol-Version` e `Mcp-Method` em todo request MCP, e SHALL emitir `Mcp-Name` nos requests `tools/call` e `resources/read`, com valor igual ao do corpo correspondente (nome da tool e URI do resource, respectivamente).

#### Scenario: headers espelham o corpo

- **WHEN** o agente emite `tools/list`, `resources/read` de `politica://uso` e `tools/call` de `reservar_sala`
- **THEN** os três carregam `MCP-Protocol-Version` e `Mcp-Method` coerentes com o corpo
- **AND** `resources/read` carrega `Mcp-Name: politica://uso` e `tools/call` carrega `Mcp-Name: reservar_sala`

### Requirement: Interpretação determinística do pedido

O agente SHALL interpretar o pedido em formato fixo `reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>` por regra, sem LLM e sem nenhum componente de modelo de linguagem no caminho de execução. Dado o mesmo pedido, o agente MUST produzir o mesmo resultado.

#### Scenario: pedido válido é interpretado

- **WHEN** o agente recebe `reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 fim=2026-11-03T15:00:00-03:00 responsavel=Marty`
- **THEN** ele chama `reservar_sala` com `sala=sala-garagem`, `inicio`, `fim` e `responsavel=Marty`

#### Scenario: determinismo

- **WHEN** o mesmo pedido é submetido duas vezes com o servidor no mesmo estado inicial
- **THEN** o agente produz o mesmo resultado nas duas execuções

### Requirement: Resultado tipado do ciclo de reserva

O agente SHALL devolver um resultado tipado com uma das três formas: reserva criada (com o campo `politica`), pausa (`input_required` cru, com `inputRequests` e `requestState` guardados sem interpretar) ou falha (mensagem exata da tool).

#### Scenario: reserva criada

- **WHEN** `reservar_sala` conclui sem conflito
- **THEN** o resultado é "reserva criada" com os dados da reserva e o campo `politica` lido do resource

#### Scenario: pausa por input_required

- **WHEN** `reservar_sala` devolve `resultType` igual a `input_required`
- **THEN** o resultado é "pausa", guardando o `inputRequests` e o `requestState` crus, sem abrir nem interpretar

#### Scenario: falha com a mensagem da tool

- **WHEN** `reservar_sala` devolve `isError` verdadeiro
- **THEN** o resultado é "falha" com a mensagem exata devolvida pela tool

### Requirement: requestState opaco

O agente SHALL tratar o `requestState` como opaco: guardar e ecoar, nunca abrir, interpretar nem reconstruir, mesmo que o conteúdo seja legível.

#### Scenario: requestState é ecoado sem modificação

- **WHEN** a pausa guarda um `requestState` e a continuação refaz o `tools/call`
- **THEN** o `requestState` enviado no retry é idêntico (byte a byte) ao recebido
- **AND** o agente não examina o conteúdo dele em nenhum ponto

### Requirement: Continuação da reserva

Dado um pedido que pausou, o agente SHALL permitir continuar com uma escolha, refazendo o `tools/call` de `reservar_sala` com um id JSON-RPC **novo**, `inputResponses` usando a **mesma chave** que veio no `inputRequests` e o `requestState` ecoado sem modificação. A escolha `recusar` SHALL ser traduzida para `action` igual a `decline`.

#### Scenario: continuação com escolha

- **WHEN** o agente continua uma pausa com `escolha=sala-fusca`
- **THEN** ele emite um `tools/call` com id diferente do request inicial
- **AND** `inputResponses` traz a mesma chave do `inputRequests` com `action=accept` e `content.sala=sala-fusca`
- **AND** o resultado devolvido é o da tool (reserva criada ou falha)

#### Scenario: recusa

- **WHEN** o agente continua uma pausa com `escolha=recusar`
- **THEN** ele emite um `tools/call` com `inputResponses` trazendo `action=decline`
- **AND** o resultado devolvido reflete a recusa, sem criar reserva
