# Spec Delta

## Purpose

Define a costura entre o `input_required` do servidor MCP e a Task do agente A2A: a pausa em `TASK_STATE_INPUT_REQUIRED` com a lista de alternativas na ordem do `enum`, o `requestState` guardado e amarrado ao `taskId` sem nunca ser exposto, e a retomada via `escolha=<id>`/`escolha=recusar`.

## ADDED Requirements

### Requirement: Pausa da Task por input_required

Quando o servidor MCP responde `input_required` (o `InputRequiredResult` cru), o agente SHALL colocar a Task em `TASK_STATE_INPUT_REQUIRED` e SHALL devolver, como mensagem de status da Task, exatamente a linha `alternativas: <ids separados por virgula e espaco>`, com os ids na mesma ordem em que vieram no `enum` da elicitation. A linha SHALL NOT ter prefixo, saudação nem qualquer texto adicional.

#### Scenario: conflito pausa a Task com a linha de alternativas

- **WHEN** um `SendMessage` pede uma sala ocupada e o servidor MCP devolve `input_required` com uma elicitation em form mode cujo `enum` é `["sala-fusca", "sala-mirante"]`
- **THEN** a resposta devolve a Task em `TASK_STATE_INPUT_REQUIRED`
- **AND** a mensagem de status contém exatamente `alternativas: sala-fusca, sala-mirante`

#### Scenario: ordem das alternativas segue o enum

- **WHEN** a elicitation traz `enum` igual a `["sala-fusca", "sala-mirante"]`
- **THEN** a linha de alternativas lista os ids exatamente nessa ordem, separados por virgula e espaco

### Requirement: requestState amarrado à Task e não exposto

O `requestState` recebido do servidor MCP SHALL ficar guardado no agente associado ao `taskId` daquela Task. O `requestState` SHALL NOT aparecer em nenhuma resposta A2A devolvida ao cliente — nem no Agent Card, nem no artifact, nem em qualquer mensagem de status ou entrada do `history`.

#### Scenario: requestState fica preso à Task e nunca vaza

- **WHEN** uma Task entra em `TASK_STATE_INPUT_REQUIRED` com um `requestState` opaco
- **THEN** nenhum campo de nenhuma resposta A2A (card, `result.task` de `SendMessage` ou `GetTask`) contém o texto do `requestState`
- **AND** a continuação da Task usa o `requestState` guardado para aquela Task

### Requirement: Continuação dentro do enum conclui a reserva

Um `SendMessage` de continuação que referencia uma Task pausada (via `taskId`) e traz o texto `escolha=<id>` cujo `<id>` está no `enum` SHALL refazer o `tools/call` ao servidor MCP com um id JSON-RPC **diferente** do request inicial, levando `inputResponses` com a **mesma chave** que veio no `inputRequests` e o `requestState` ecoado **sem modificação**. A Task SHALL então terminar em `TASK_STATE_COMPLETED` com o artifact `reserva` na sala escolhida.

#### Scenario: escolha válida conclui na sala escolhida

- **WHEN** um `SendMessage` referencia uma Task pausada com `escolha=sala-fusca` e `sala-fusca` está no `enum`
- **THEN** o agente refaz o `tools/call` com id JSON-RPC novo, `inputResponses` com a mesma chave do `inputRequests` e o `requestState` inalterado
- **AND** a Task termina em `TASK_STATE_COMPLETED` com o artifact `reserva` cujo `sala` é `sala-fusca`

#### Scenario: id do retry difere do request inicial

- **WHEN** o agente retoma uma pausa com uma escolha válida
- **THEN** o id JSON-RPC do retry ao `tools/call` é diferente do id do `tools/call` inicial daquela Task

### Requirement: Escolha fora do enum mantém a pausa

Um `SendMessage` de continuação com `escolha=<id>` cujo `<id>` **não** está no `enum` SHALL manter a Task em `TASK_STATE_INPUT_REQUIRED` e SHALL repetir a linha `alternativas: <ids>` na ordem do `enum`, sem chamar o servidor MCP.

#### Scenario: escolha inválida repete as alternativas

- **WHEN** um `SendMessage` referencia uma Task pausada com `escolha=sala-aquario` e `sala-aquario` não está no `enum`
- **THEN** a Task permanece em `TASK_STATE_INPUT_REQUIRED`
- **AND** a mensagem de status repete a linha `alternativas: <ids na ordem do enum>`

### Requirement: Recusa termina a Task em CANCELED

Um `SendMessage` de continuação com o texto `escolha=recusar` SHALL transformar a escolha em `action` igual a `decline` na elicitation, SHALL reenviar ao servidor MCP com id JSON-RPC novo e o `requestState` ecoado, e a Task SHALL terminar em `TASK_STATE_CANCELED` (reserva não criada, sem `isError`).

#### Scenario: recusa cancela a Task

- **WHEN** um `SendMessage` referencia uma Task pausada com `escolha=recusar`
- **THEN** o agente reenvia ao MCP com `action` igual a `decline`
- **AND** a Task termina em `TASK_STATE_CANCELED`

### Requirement: Estado pausado é por Task

O estado pausado (a reserva guardada e o `requestState` associado) SHALL ser por Task: duas Tasks pausadas ao mesmo tempo SHALL concluir cada uma com a sua própria reserva, sem trocar de `requestState`.

#### Scenario: duas Tasks pausadas não trocam requestState

- **WHEN** duas Tasks de pedidos distintos estão em `TASK_STATE_INPUT_REQUIRED` ao mesmo tempo, cada uma com o seu `requestState`
- **THEN** a continuação de cada uma usa o `requestState` guardado para aquela Task
- **AND** cada Task termina em `TASK_STATE_COMPLETED` com a sua própria reserva (reserva e inicio distintos), sem cruzar os `requestState`
