# Spec Delta

## Purpose

Define o contrato observável do servidor MCP da Hill Valley Tech na fase base: transporte Streamable HTTP sem sessão, exigência de metadados por request, catálogo das três tools de salas, validações de política com mensagens literais, resource da política e log em stderr — sem MRTR.

## ADDED Requirements

### Requirement: Endpoint Streamable HTTP sem sessão

O servidor SHALL atender em Streamable HTTP no endpoint único `/mcp`, na porta `7301` por padrão (parametrizável por variável de ambiente), em modo stateless: cada request MUST ser tratado de forma independente, sem sessão, sem estado de protocolo guardado entre requests e sem inferir versão ou capabilities de request anterior.

#### Scenario: Descoberta responde na porta padrão

- **WHEN** um cliente envia `POST http://localhost:7301/mcp` com `tools/list` e os metadados obrigatórios
- **THEN** o servidor responde `200` com um resultado JSON-RPC contendo as tools
- **AND** nenhum identificador de sessão é exigido para o próximo request

#### Scenario: Requests independentes

- **WHEN** dois requests consecutivos chegam sem sessão compartilhada
- **THEN** cada um é avaliado apenas com os próprios metadados
- **AND** o segundo não herda versão nem capabilities do primeiro

### Requirement: Metadados obrigatórios por request

O servidor SHALL rejeitar com erro JSON-RPC `-32602` e HTTP `400` qualquer request cujo `params._meta` não contenha `io.modelcontextprotocol/protocolVersion` ou `io.modelcontextprotocol/clientCapabilities`. A verificação MUST ocorrer por request, antes da execução do método, sem tentar inferir os valores ausentes.

#### Scenario: Sem protocolVersion

- **WHEN** um `tools/call` chega com `_meta` sem `io.modelcontextprotocol/protocolVersion`
- **THEN** o servidor responde HTTP `400` com `error.code` igual a `-32602`
- **AND** a tool não é executada

#### Scenario: Sem clientCapabilities

- **WHEN** um `tools/call` chega com `_meta` sem `io.modelcontextprotocol/clientCapabilities`
- **THEN** o servidor responde HTTP `400` com `error.code` igual a `-32602`
- **AND** a tool não é executada

### Requirement: Capabilities declaradas

O servidor SHALL declarar as capabilities `tools` e `resources` na negociação do protocolo.

#### Scenario: Capabilities visíveis na inicialização

- **WHEN** um cliente completa a negociação inicial do protocolo
- **THEN** a resposta declara `tools` e `resources` como capabilities do servidor

### Requirement: Catálogo de tools

O servidor SHALL publicar em `tools/list` exatamente as tools `listar_salas`, `consultar_disponibilidade` e `reservar_sala`. Toda tool MUST declarar um `inputSchema` cujo `type` é `object` e que é um JSON Schema válido. Nenhuma tool SHALL exigir parâmetro fora do seu `inputSchema`.

#### Scenario: As três tools são descobertas

- **WHEN** o cliente envia `tools/list`
- **THEN** o resultado contém `listar_salas`, `consultar_disponibilidade` e `reservar_sala`

#### Scenario: inputSchema é objeto

- **WHEN** o cliente inspeciona cada tool retornada por `tools/list`
- **THEN** toda tool tem `inputSchema.type` igual a `object`
- **AND** `listar_salas` aceita `{}` como argumentos

### Requirement: listar_salas com structuredContent e texto

`listar_salas` SHALL devolver todas as salas de `dados/salas.json`, cada uma com `id`, `nome`, `capacidade` e `recursos`, em `structuredContent` conforme o `outputSchema` declarado, e SHALL devolver o mesmo JSON serializado em um bloco de texto do resultado.

#### Scenario: Conteúdo estruturado e textual idênticos

- **WHEN** o cliente chama `listar_salas` com argumentos vazios
- **THEN** o resultado traz `structuredContent` com a lista `salas`
- **AND** o texto do resultado, quando desserializado, é igual ao `structuredContent`
- **AND** o `outputSchema` da tool descreve esse formato

### Requirement: consultar_disponibilidade

`consultar_disponibilidade` SHALL receber `sala`, `inicio` e `fim` e devolver `sala`, `livre` e `conflitos`, onde `conflitos` lista as reservas sobrepostas com `id`, `inicio`, `fim` e `responsavel`. Intervalos que apenas se tocam não SHALL ser considerados conflito. A tool SHALL aplicar as mesmas validações de sala e de política da reserva e devolver os mesmos erros de execução.

#### Scenario: Intervalo livre

- **WHEN** o cliente consulta uma sala existente em um intervalo sem sobreposição
- **THEN** `livre` é `true` e `conflitos` é vazio

#### Scenario: Intervalo ocupado

- **WHEN** o cliente consulta `sala-garagem` em `2026-11-03T14:00:00-03:00`–`2026-11-03T15:00:00-03:00`, intervalo da reserva `res-0001`
- **THEN** `livre` é `false`
- **AND** `conflitos` contém a reserva `res-0001` com o responsável

#### Scenario: Validação de política na consulta

- **WHEN** a consulta viola sala, janela, duração ou ordem do intervalo
- **THEN** o resultado tem `isError` verdadeiro com a mensagem exata correspondente
- **AND** nenhum `structuredContent` de disponibilidade é devolvido como sucesso

### Requirement: reservar_sala no caminho feliz

`reservar_sala` SHALL receber `sala`, `inicio`, `fim` e `responsavel` e, quando o intervalo está livre e dentro da política, SHALL criar a reserva e devolver `resultType` igual a `complete` com `structuredContent` contendo `reserva`, `reservado`, `sala`, `inicio`, `fim`, `responsavel`, `politica` e `motivo`, além do mesmo JSON em um bloco de texto. A reserva criada MUST ser visível nas consultas seguintes do mesmo processo. `politica` MUST conter a versão declarada na primeira linha de `dados/politica-de-uso.md`.

#### Scenario: Reserva criada

- **WHEN** o cliente reserva uma sala existente em intervalo livre e dentro da política
- **THEN** o resultado é `complete`, `isError` é falso e `reservado` é `true`
- **AND** `reserva` vem preenchido e `politica` é `2026-11-01`

#### Scenario: Reserva visível depois

- **WHEN** o cliente consulta a disponibilidade do mesmo intervalo após criar a reserva
- **THEN** o intervalo aparece como não livre com a reserva recém-criada em `conflitos`

#### Scenario: Conflito sem alternativa

- **WHEN** o intervalo conflita e nenhuma sala alternativa atende à regra de alternativas
- **THEN** o resultado tem `isError` verdadeiro com a mensagem `Sem alternativas disponiveis no intervalo`
- **AND** nenhuma reserva é criada

### Requirement: Validações de política com mensagens exatas

As tools de reserva e de consulta SHALL validar, nesta ordem: existência da sala; `fim` posterior a `inicio`; `inicio` e `fim` dentro da janela 08:00–20:00 em `-03:00`; duração máxima de 2 horas. As falhas SHALL ser erros de execução (`isError: true`) com o texto literal do enunciado.

#### Scenario: Sala inexistente

- **WHEN** o cliente reserva `sala-delorean`
- **THEN** o resultado tem `isError` verdadeiro e contém `Sala inexistente: sala-delorean`

#### Scenario: Fora da janela

- **WHEN** o cliente consulta `sala-aquario` em `2026-11-03T07:00:00-03:00`–`2026-11-03T08:00:00-03:00`
- **THEN** o resultado tem `isError` verdadeiro e contém `Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00`

#### Scenario: Duração acima do limite

- **WHEN** o cliente consulta `sala-aquario` em `2026-11-03T09:00:00-03:00`–`2026-11-03T12:00:00-03:00`
- **THEN** o resultado tem `isError` verdadeiro e contém `Duracao acima do limite: a politica permite no maximo 2 horas`

#### Scenario: Intervalo invertido

- **WHEN** o cliente consulta `sala-aquario` em `2026-11-03T10:00:00-03:00`–`2026-11-03T09:00:00-03:00`
- **THEN** o resultado tem `isError` verdadeiro e contém `Intervalo invalido: fim deve ser posterior a inicio`

### Requirement: Resource da política de uso

O servidor SHALL expor o resource `politica://uso` com o conteúdo integral de `dados/politica-de-uso.md` e `mimeType` igual a `text/markdown`. A leitura de qualquer outra URI SHALL ser recusada com erro JSON-RPC `-32602`, sem devolver `contents` vazio.

#### Scenario: Leitura da política

- **WHEN** o cliente envia `resources/read` para `politica://uso`
- **THEN** `contents` traz um item com `uri` `politica://uso`, `mimeType` `text/markdown` e o texto da política

#### Scenario: URI inexistente

- **WHEN** o cliente envia `resources/read` para `politica://inexistente`
- **THEN** a resposta é um `error` JSON-RPC com `code` `-32602`
- **AND** nenhum `contents` é devolvido

### Requirement: Log em stderr por request

O servidor SHALL registrar no stderr, para cada request recebido, no mínimo o método, o id e o `traceparent` quando presente em `params._meta`. O registro MUST ocorrer também para requests rejeitados antes do despacho. A ausência de `traceparent` MUST ser registrada de forma explícita, sem omitir a linha.

#### Scenario: Request com traceparent

- **WHEN** um request chega com `params._meta.traceparent` igual a `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
- **THEN** o stderr contém uma linha com o método, o id do request e esse traceparent

#### Scenario: Request rejeitado também é logado

- **WHEN** um request chega sem `io.modelcontextprotocol/protocolVersion`
- **THEN** o stderr registra método e id mesmo que a resposta seja `-32602` com HTTP `400`
