# Spec Delta

## ADDED Requirements

### Requirement: Conflito devolve input_required

`reservar_sala` SHALL, quando o intervalo pedido conflita com uma reserva existente e existe ao menos uma sala alternativa, devolver um resultado com `resultType` igual a `input_required` em vez de `isError`. O resultado MUST conter `inputRequests` com uma única entrada cujo valor é um request `elicitation/create` em `mode` form, e um `requestState` presente. A chave da entrada em `inputRequests` é atribuída pelo servidor, e o cliente MUST devolver exatamente a mesma chave no `inputResponses` do retry. O `requestedSchema` SHALL ser um objeto plano com uma propriedade `sala` do tipo string restrita por `enum` às salas alternativas calculadas pela regra do enunciado, na ordem definida (capacidade crescente e, em empate, `id` em ordem alfabética).

#### Scenario: Conflito pede a escolha

- **WHEN** o cliente reserva `sala-garagem` em `2026-11-03T14:00:00-03:00`–`2026-11-03T15:00:00-03:00`, intervalo já ocupado por `res-0001`, com a capability de elicitation em form mode declarada
- **THEN** o resultado tem `resultType` igual a `input_required`
- **AND** `inputRequests` tem exatamente uma entrada, cujo valor tem `method` `elicitation/create` e `params.mode` `form`
- **AND** `params.requestedSchema` é um objeto plano com `properties.sala.type` `string` e `enum` igual a `["sala-fusca", "sala-mirante"]`
- **AND** `requestState` está presente e não vazio

#### Scenario: Sem alternativa não há elicitation

- **WHEN** o intervalo conflita e nenhuma sala alternativa atende à regra de alternativas
- **THEN** o resultado tem `isError` verdadeiro com a mensagem `Sem alternativas disponiveis no intervalo`
- **AND** não há `input_required` nem `requestState`

### Requirement: requestState selado e expirado

O `requestState` SHALL ser protegido por integridade usando o `RequestStateBoundary` do SDK com `RequestStateSecurity(keys=[...], ttl=900)`, de modo que uma adulteração seja detectada. A chave MUST vir da variável de ambiente `REQUEST_STATE_SECRET` e ter no mínimo 32 bytes; nenhuma chave SHALL ser hardcoded no código. Se a variável estiver ausente ou a chave for curta demais, o processo MUST falhar na subida com mensagem clara. O `requestState` MUST carregar tudo o que o servidor precisa para reconstruir o pedido (sala, início, fim, responsável e alternativas), de modo que um retry apresentado após a reinicialização do processo seja aceito.

#### Scenario: Chave ausente falha na subida

- **WHEN** o processo é iniciado sem `REQUEST_STATE_SECRET` definida no ambiente
- **THEN** a subida falha com mensagem clara indicando a variável ausente
- **AND** o servidor não fica escutando na porta

#### Scenario: Retry sobrevive a reinicialização

- **WHEN** o servidor devolve um `requestState` e é reiniciado antes do retry
- **THEN** o retry com aquele `requestState` é aceito e a reserva é concluída

### Requirement: Capability de elicitation é exigida

O servidor SHALL recusar um pedido de reserva em conflito vindo de cliente que não declarou a capability de elicitation em form mode. Nesse caso a resposta MUST ser um erro JSON-RPC `-32021` com `data.requiredCapabilities` listando a capability ausente, e o status HTTP MUST ser `400`.

#### Scenario: Conflito sem capability declarada

- **WHEN** o cliente reserva `sala-garagem` em `2026-11-03T14:00:00-03:00`–`2026-11-03T15:00:00-03:00` com `clientCapabilities` vazio
- **THEN** a resposta é um erro com `code` `-32021`
- **AND** `data.requiredCapabilities` contém `elicitation.form`
- **AND** o status HTTP é `400`

### Requirement: Retry reconstrói o pedido a partir do estado selado

No retry, o servidor SHALL ler `inputResponses` e `requestState` de dentro de `params`, reconstruir o pedido original a partir do próprio `requestState` (não dos argumentos reenviados) e concluir a operação. Com `action` `accept`, o resultado MUST ser `resultType` igual a `complete`, sem `isError`, com o `structuredContent` contendo `reserva`, `reservado`, `sala`, `inicio`, `fim`, `responsavel`, `politica` e `motivo`, e com a sala escolhida em `inputResponses`.

#### Scenario: Retry aceito conclui na sala escolhida

- **WHEN** o cliente repete o `tools/call` com `inputResponses` trazendo a mesma chave do `inputRequests` e `action` `accept` com `content.sala` igual a `sala-fusca`, mais o `requestState` ecoado sem modificação
- **THEN** o resultado é `complete`, sem `isError`
- **AND** `structuredContent.sala` é `sala-fusca` e `reservado` é `true`

### Requirement: Recusa conclui sem reservar

Um retry com `action` igual a `decline` ou `cancel` SHALL concluir sem criar reserva, sem `isError` (ausente ou `false`), devolvendo `resultType` igual a `complete` com `structuredContent.reservado` igual a `false` e um `motivo` preenchido.

#### Scenario: Recusa do usuário

- **WHEN** o cliente repete o `tools/call` com `inputResponses` trazendo `action` `decline` e o `requestState` válido
- **THEN** o resultado é `complete` e `isError` é falso ou ausente
- **AND** `structuredContent.reservado` é `false` e `motivo` está presente
- **AND** nenhuma reserva é criada

### Requirement: requestState inválido é rejeitado

Um `requestState` adulterado, expirado ou reapresentado com argumentos diferentes dos selados SHALL ser rejeitado com erro JSON-RPC `-32602`. O handler MUST deixar a rejeição do `RequestStateBoundary` propagar, sem engolir o erro nem converter em erro de execução.

#### Scenario: Adulteração é detectada

- **WHEN** o cliente reenvia um `requestState` com um caractere alterado
- **THEN** a resposta é um erro com `code` `-32602`

#### Scenario: Argumentos divergentes não tomam efeito

- **WHEN** o retry reenvia argumentos (`sala`, `inicio`, `fim`, `responsavel`) diferentes dos que foram selados
- **THEN** a resposta é um erro `-32602` ou a reserva é concluída usando os valores selados
- **AND** em nenhum caso a reserva é criada com os valores adulterados
