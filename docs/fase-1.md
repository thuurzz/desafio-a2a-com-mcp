# Fase 1 — Servidor MCP base

Branch: `spec-fase-1-servidor-mcp` (partindo de `fase-1-servidor-mcp-base`, que já tem o commit do OpenSpec).

## Como testar

Na fase 1 o agente A2A ainda não existia, então só o lado MCP está em jogo. A forma atual de medir tudo
(as seis fases) é `./scripts/progresso.sh`, que sobe os dois processos do zero em portas isoladas e roda o
validador oficial — na fase 1 ele mostra 13/36, com as verificações 01 a 12 e a 20 verdes.

Para inspecionar só o servidor MCP na mão (porta `7301`, endpoint `/mcp`), suba com o segredo exportado:

```bash
export REQUEST_STATE_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
.venv/bin/python servidor-mcp/main.py
```

e mande os requests de `exemplos/wire/01` a `05` com `curl`.

Para testar pela rede local (outro notebook/celular), suba com bind explícito:

```bash
MCP_HOST=0.0.0.0 MCP_PORT=7301 .venv/bin/python servidor-mcp/main.py
```

O SDK protege contra DNS rebinding e devolve HTTP `421` para Host não declarado; com `MCP_HOST` fora do loopback o app libera automaticamente as IPs da máquina (e aceita extras em `MCP_ALLOWED_HOSTS`).

- [x] 01. Projeto `servidor-mcp/`: `pyproject.toml` lendo `dados/` em modo somente leitura (lê 5 salas, 2 reservas, política `2026-11-01`).
- [x] 02. Streamable HTTP stateless em `/mcp` na porta `7301` (`json_response=True`, `stateless_http=True`) — `curl POST /mcp` devolve `200`.
- [x] 03. `_meta` obrigatório por request: sem `protocolVersion` ou sem `clientCapabilities` → `-32602` + HTTP `400` (PASS 04 e 05).
- [x] 04. `tools/list` com as 3 tools e `inputSchema` objeto (PASS 01, 02); `listar_salas` com `outputSchema` + `structuredContent` idêntico ao bloco de texto (PASS 03).
- [x] 05. `consultar_disponibilidade` com as 4 validações de política e as mensagens literais (PASS 09 a 12).
- [x] 06. `reservar_sala` no caminho feliz (structuredContent com `reserva`, `reservado`, `sala`, `inicio`, `fim`, `responsavel`, `politica`) e conflito sem alternativa (PASS 20).
- [x] 07. Resource `politica://uso` (`text/markdown`) e URI inexistente → `-32602` (PASS 07, 08).
- [x] 08. Log em stderr com método, id e `traceparent` de cada request (`mcp request metodo=... id=... traceparent=...`).
- [x] 09. Tool inexistente recusada (PASS 06).

## Saída real do validador (fase 1)

```
trace-id desta execucao: 8062f4aa2fa0611c66b679a1a5986bbb
procure esse valor no stderr do servidor MCP para conferir a propagacao do traceparent.

PASS 01 tools/list traz as tres tools
PASS 02 toda tool tem inputSchema de objeto
PASS 03 listar_salas devolve structuredContent e o mesmo JSON em texto
PASS 04 _meta sem protocolVersion devolve -32602 e HTTP 400
PASS 05 _meta sem clientCapabilities devolve -32602 e HTTP 400
PASS 06 tool inexistente e recusada, por -32602 ou por isError
PASS 07 resources/read de politica://uso devolve a politica
PASS 08 resources/read de URI inexistente devolve -32602
PASS 09 sala inexistente devolve isError com a mensagem exata
PASS 10 fora da janela devolve isError com a mensagem exata
PASS 11 duracao acima de 2h devolve isError com a mensagem exata
PASS 12 intervalo invertido devolve isError com a mensagem exata
FAIL 13 conflito devolve input_required com inputRequests e requestState: resultType=complete chaves=[]
FAIL 14 a elicitation e form mode e oferece as alternativas na ordem certa: nenhum inputRequest para inspecionar
FAIL 15 conflito sem a capability elicitation devolve -32021 e HTTP 400: code=None http=200 data={}
FAIL 16 retry com inputResponses e requestState conclui a reserva: conflito de 16h nao pediu input
FAIL 17 requestState adulterado e rejeitado com -32602: sem requestState do passo 13
FAIL 18 requestState apresentado em outra tool e rejeitado: sem requestState do passo 13
FAIL 19 recusa conclui sem reservar e sem isError: sem requestState do passo 13
PASS 20 conflito sem alternativa possivel devolve isError com a mensagem exata

FAIL 21 a 36: agente A2A ainda nao existe (Connection refused na 7300)
```

Contagem: **13 PASS, 23 FAIL** — todos os FAIL são de escopo das fases seguintes.

## Pendências conhecidas (entram na fase 2)

- O ciclo de MRTR (`input_required`, elicitation form mode, `requestState` selado com `RequestStateSecurity`/`REQUEST_STATE_SECRET`), que resolve PASS 13 a 19.
- Hoje, conflito **com** alternativas devolve `isError` transitório (`Conflito com alternativas: ...`) em `controllers/salas.py::reservar` — na fase 2 esse ramo vira `InputRequiredResult` e a regra de alternativas continua no controller.
