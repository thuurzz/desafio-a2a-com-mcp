# Delta de spec — entrega

## ADDED Requirements

### Requirement: Documentação executável da entrega
O repositório DEVE conter um `README.md` que permita a uma pessoa subir os dois processos e rodar o validador a partir de um clone limpo, sem consultar outra fonte.

#### Scenario: Clone limpo seguindo apenas o README
- **GIVEN** um clone novo do repositório em pasta vazia
- **WHEN** a pessoa executa os comandos do README na ordem apresentada
- **THEN** o servidor MCP responde em `:7301/mcp` e o agente responde em `:7300/.well-known/agent-card.json`
- **AND** `validador/validar.py` termina com 36 verificações passando e código de saída 0

### Requirement: Origem do segredo do requestState documentada
O README DEVE documentar como gerar e exportar `REQUEST_STATE_SECRET`, sem publicar nenhum valor.

#### Scenario: Chave ausente impede a subida
- **GIVEN** o ambiente sem `REQUEST_STATE_SECRET`
- **WHEN** o servidor MCP é iniciado
- **THEN** o processo falha com mensagem clara antes de escutar na porta
- **AND** nenhum valor de chave aparece no repositório

### Requirement: Seção que localiza a ponte
O README DEVE apontar o ponto exato do código em que o `input_required` do MCP vira pausa da Task e o ponto em que o `requestState` volta ao servidor.

#### Scenario: Leitor encontra a costura
- **GIVEN** o README aberto na seção da ponte
- **WHEN** o leitor segue os caminhos citados
- **THEN** encontra a tradução do `Pausado` para `TASK_STATE_INPUT_REQUIRED` e o registro do `requestState` por `taskId`
- **AND** encontra o retry que envia `inputResponses` com o `requestState` ecoado
