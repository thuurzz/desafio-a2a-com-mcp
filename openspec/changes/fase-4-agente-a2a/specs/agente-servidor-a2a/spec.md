# Spec Delta

## Purpose

Define o contrato observável do agente atuando como servidor A2A v1.0: publicação do Agent Card no well-known URI, atendimento de `SendMessage` e `GetTask` em JSON-RPC 2.0 sobre `/a2a`, a máquina de estados da Task com artifact `reserva` e terminalidade definitiva, e a tradução do erro de execução da tool para `TASK_STATE_FAILED`.

## ADDED Requirements

### Requirement: Agent Card no well-known URI

O agente SHALL responder a `GET /.well-known/agent-card.json` com HTTP `200` e um corpo JSON válido na forma da A2A v1.0, declarando a identidade, a interface JSON-RPC (com a URL do endpoint e a versão de protocolo `1.0`), as capabilities e a skill `reservar-sala`.

#### Scenario: card v1.0 no well-known

- **WHEN** um cliente faz `GET /.well-known/agent-card.json`
- **THEN** a resposta tem status `200` e o corpo é um objeto JSON
- **AND** o objeto contém `supportedInterfaces` com ao menos uma entrada cujo `protocolBinding` começa com `JSONRPC`, com `url` preenchida apontando para o endpoint `/a2a` e `protocolVersion` começando com `1.0`

#### Scenario: skill de reserva declarada

- **WHEN** o Agent Card é lido
- **THEN** a lista `skills` contém uma entrada com `id` igual a `reservar-sala`

### Requirement: Endpoint JSON-RPC com SendMessage e GetTask

O agente SHALL aceitar `POST /a2a` com corpo JSON-RPC 2.0 (`jsonrpc`, `id`, `method`, `params`) e SHALL responder no mesmo envelope, ecoando o `id` do request. Os métodos suportados SHALL ser `SendMessage` e `GetTask`.

#### Scenario: envelope JSON-RPC ecoando o id

- **WHEN** um cliente envia `POST /a2a` com `{"jsonrpc": "2.0", "id": <id>, "method": "SendMessage", "params": {...}}`
- **THEN** a resposta traz `jsonrpc` igual a `2.0`, `id` igual ao recebido e `result` com a Task

### Requirement: Abertura de Task por SendMessage

Um `SendMessage` cujo `message` não traz `taskId` SHALL abrir uma Task nova, com `id` e `contextId` próprios gerados pelo agente, e SHALL registrar a mensagem do usuário no histórico da Task.

#### Scenario: Task nova com identidade própria

- **WHEN** o agente recebe um `SendMessage` sem `taskId` com um pedido de reserva
- **THEN** a resposta contém uma Task com `id` não vazio e `contextId` não vazio
- **AND** o histórico contém a mensagem do usuário com `role` igual a `ROLE_USER`

### Requirement: Máquina de estados da Task

A Task SHALL transitar por `TASK_STATE_SUBMITTED` e `TASK_STATE_WORKING` antes de chegar a um estado terminal. Os estados terminais SHALL ser `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED` e `TASK_STATE_CANCELED`. A resposta de um `SendMessage` que executa o pedido de forma síncrona SHALL refletir o estado terminal alcançado.

#### Scenario: estados transitórios antes do terminal

- **WHEN** um `SendMessage` abre uma Task e executa o pedido
- **THEN** a Task passa por `TASK_STATE_SUBMITTED` e `TASK_STATE_WORKING` antes de terminar
- **AND** a resposta devolve a Task no seu estado terminal corrente

### Requirement: Artifact de reserva concluída

Quando a reserva é concluída com sucesso, a Task SHALL terminar em `TASK_STATE_COMPLETED` com um artifact de `name` igual a `reserva`, cujo conteúdo é o JSON da reserva criada, incluindo o campo `politica` com a versão lida do resource.

#### Scenario: artifact com a reserva e a versão da política

- **WHEN** um `SendMessage` pede uma sala livre e o servidor MCP conclui a reserva
- **THEN** a Task termina em `TASK_STATE_COMPLETED`
- **AND** `artifacts` contém um artifact com `name` igual a `reserva`
- **AND** o JSON do artifact traz `reserva`, `sala`, `inicio`, `fim`, `responsavel` e `politica` igual a `2026-11-01`

### Requirement: GetTask devolve o estado corrente

Um `GetTask` com o `id` de uma Task SHALL devolver o `id`, o `contextId`, o estado corrente, o `history` e os `artifacts` daquela Task.

#### Scenario: GetTask reflete a Task

- **WHEN** um cliente envia `GetTask` com o `id` de uma Task concluída
- **THEN** a resposta contém `id` igual ao pedido, `contextId` não vazio, `status.state` igual a `TASK_STATE_COMPLETED` e o artifact presente

### Requirement: Terminalidade definitiva da Task

Uma Task em estado terminal (`COMPLETED`, `FAILED` ou `CANCELED`) SHALL NOT voltar a `WORKING`. Um `SendMessage` cujo `message` referencia uma Task em estado terminal SHALL ser recusado com erro JSON-RPC.

#### Scenario: SendMessage em Task terminal é recusado

- **WHEN** um `SendMessage` referencia (via `taskId`) uma Task já em estado terminal
- **THEN** a resposta é um erro JSON-RPC (com o campo `error`, sem `result`)

### Requirement: Falha da tool termina a Task em FAILED

Quando a tool do servidor MCP devolve `isError` verdadeiro, o agente SHALL terminar a Task em `TASK_STATE_FAILED` e SHALL expor a mensagem exata devolvida pela tool na mensagem de status e no histórico da Task.

#### Scenario: sala inexistente termina em FAILED com a mensagem da tool

- **WHEN** um `SendMessage` pede uma sala inexistente e a tool devolve `isError` com `Sala inexistente: <id>`
- **THEN** a Task termina em `TASK_STATE_FAILED`
- **AND** a mensagem de status da Task contém o texto exato `Sala inexistente: <id>`

### Requirement: Propagação do traceparent

Quando a chamada A2A de entrada traz o header `traceparent`, o agente SHALL propagar o mesmo trace-id nos requests MCP emitidos para executar aquele pedido (o span-id pode ser novo).

#### Scenario: trace-id preservado até o MCP

- **WHEN** um `SendMessage` chega com o header `traceparent` com um trace-id
- **THEN** os requests MCP emitidos para aquele pedido carregam um `traceparent` com o mesmo trace-id
