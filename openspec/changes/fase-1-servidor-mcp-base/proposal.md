# Proposal

## Why

O starter do desafio não traz código de aplicação: `servidor-mcp/` e `agente/` chegam vazios, e a fonte de verdade do contrato são `README.md`, `exemplos/wire/` e `validador/validar.py`. Sem uma base de servidor MCP em Streamable HTTP, stateless e com o contrato de tools/resource já fechado, as fases seguintes (MRTR com `requestState`, agente host MCP, servidor A2A e a ponte) não têm onde se apoiar. Esta fase entrega essa base e faz o validador avançar nas verificações puramente MCP.

## What Changes

- Cria o projeto Python em `servidor-mcp/` com `pyproject.toml`, dependência `mcp>=2.3,<3` (SDK oficial v2) e o layout `models/` (schemas e estado), `controllers/` (regras de negócio e leitura de `dados/`) e `views/` (superfície HTTP/Streamable HTTP e handlers do servidor).
- Sobe o servidor MCP em Streamable HTTP, endpoint único `/mcp`, porta padrão `7301` (parametrizável por env), em modo **stateless**: sem sessão, sem estado de protocolo entre requests e sem inferir versão/capabilities de request anterior.
- Rejeita com `-32602` e HTTP `400` qualquer request cujo `_meta` não traga `io.modelcontextprotocol/protocolVersion` ou `io.modelcontextprotocol/clientCapabilities`, na própria request.
- Declara as capabilities `tools` e `resources`.
- Publica `tools/list` com `listar_salas`, `consultar_disponibilidade` e `reservar_sala`, cada uma com `inputSchema` que é objeto JSON Schema válido; `listar_salas` e `reservar_sala` também declaram `outputSchema`.
- `listar_salas` devolve `structuredContent` conforme o `outputSchema` e o mesmo JSON serializado em bloco de texto.
- `consultar_disponibilidade` devolve `{sala, livre, conflitos}` aplicando as mesmas validações de sala e de política da reserva.
- `reservar_sala` cria a reserva no caminho feliz; conflito sem nenhuma alternativa devolve `isError` com a mensagem exata `Sem alternativas disponiveis no intervalo`.
- Aplica as quatro validações de política com as mensagens exatas do enunciado: sala inexistente, janela 08:00–20:00, duração acima de 2h e intervalo invertido.
- Expõe o resource `politica://uso` lendo `dados/politica-de-uso.md` como `text/markdown`; URI inexistente devolve `-32602`.
- Registra cada request no stderr com método, id e `traceparent` (quando presente no `_meta`).

## Não-objetivos

Fica fora desta fase, por decisão de escopo (e por estar fora de escopo ou em fase posterior no enunciado):

- MRTR: `input_required`, elicitation em form mode, `requestState`, assinatura/expiração, `-32021` e retry. Nesta fase `reservar_sala` só cobre caminho feliz e o conflito sem alternativas; conflito com alternativas não reserva nada e é substituído por `input_required` na fase 2.
- Agente como host MCP (`tools/list` em runtime, leitura do resource, headers `Mcp-Method`/`Mcp-Name`, propagação de `traceparent`).
- Agente como servidor A2A v1.0 (Agent Card, `SendMessage`, `GetTask`, máquina de estados da Task) e a ponte entre `input_required` e `TASK_STATE_INPUT_REQUIRED`.
- Autenticação/autorização (OAuth, token, `securitySchemes` real), streaming/SSE/push, prompts, subscriptions, progress, refinamento de Task e `referenceTaskIds`.
- Container, compose, deploy, gateway, spans/atributos de OpenTelemetry e interface gráfica.
- Persistência em disco das reservas criadas (memória do processo basta) e qualquer tratamento de concorrência de escrita.
- Alterar `dados/`, `validador/` ou `exemplos/` — permanecem intocados e somente leitura.

## Capabilities

### New Capabilities

- `servidor-mcp`: contrato observável do servidor MCP da Hill Valley Tech — transporte Streamable HTTP stateless em `/mcp`, rejeição de `_meta` incompleto, capabilities declaradas, catálogo e execução das três tools de salas, validações de política com mensagens exatas, resource `politica://uso` e log em stderr por request.

### Modified Capabilities

Nenhuma: o projeto ainda não possui specs em `openspec/specs/`; esta é a primeira capability.

## Impact

- **Código novo:** `servidor-mcp/` (`pyproject.toml`, `main.py` e pacotes `models/`, `controllers/`, `views/`). Nenhum outro diretório de aplicação é tocado.
- **Dependências:** `mcp>=2.3,<3` travado no `pyproject.toml`; uvicorn/starlette vêm pelo SDK. Nenhuma dependência de LLM.
- **Dados:** leitura de `dados/salas.json`, `dados/reservas.json` e `dados/politica-de-uso.md`; nenhuma escrita nesses arquivos.
- **Validador:** esta fase habilita **PASS 01–12** (tools/list, inputSchema, `listar_salas` com `structuredContent` + texto, `_meta` ausente nos dois campos, tool inexistente, resource existente/inexistente e os quatro erros de execução). Ficam **pendentes** **PASS 13–20** (dependem de MRTR, fase 2) e **PASS 21–36** (dependem do agente A2A e da ponte, fase 3).
