# Fase 2 — MRTR (elicitation + requestState)

Branch: `fase-2-mrtr`. Spec: `openspec/changes/fase-2-mrtr/` (proposal, design, tasks, spec delta — validado com `openspec validate`).
Implementação delegada ao **Claude Code** rodando `deepseek-v4-pro` através do proxy LiteLLM local (ver `docs/sdk-mcp-2.3.0.md` e o README).

## O que mudou

- `controllers/salas.py`: a regra de alternativas virou pública (`alternativas()`), agora **limitada a três**, ordenada por capacidade crescente e, no empate, por `id` alfabético. O conflito com alternativas deixou de ser texto de erro e passou a devolver `{"alternativas": [...]}`; sem alternativa continua `isError` com `Sem alternativas disponiveis no intervalo`.
- `views/servidor.py`: `reservar_sala` em conflito devolve `InputRequiredResult` com uma única entrada em `inputRequests` (`elicitation/create`, `mode=form`, `requestedSchema` plano com `enum` na ordem do controller) e `requestState` carregando o pedido original + alternativas. O retry reconstroi o pedido **do estado selado** e ignora `params.arguments`. `decline`/`cancel` conclui com `reservado=false` e `motivo`.
- `views/app.py`: `RequestStateBoundary(RequestStateSecurity(keys=[REQUEST_STATE_SECRET], ttl=900), default_audience="servidor-mcp")` registrado em `Server.middleware`. Sem a variável (ou com menos de 32 bytes) o processo **falha na subida** com mensagem clara — nenhum segredo no código.
- `views/middleware.py`: além do guard do `_meta`, o middleware agora bufferiza a resposta e reescreve o status para **HTTP 400** quando o JSON-RPC traz `error.code` em `-32021`/`-32602`.
- `-32021`: quando o cliente não declarou `elicitation.form`, o handler levanta `MCPError` com `data.requiredCapabilities` (não capturado).
- `README.md`: seção "Como rodar" com a geração/exportação de `REQUEST_STATE_SECRET` e a explicação de por que o retry sobrevive a restart.

## Evidências (execução real)

Validador com o processo recém-iniciado:

```
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
PASS 13 conflito devolve input_required com inputRequests e requestState
PASS 14 a elicitation e form mode e oferece as alternativas na ordem certa
PASS 15 conflito sem a capability elicitation devolve -32021 e HTTP 400
PASS 16 retry com inputResponses e requestState conclui a reserva
PASS 17 requestState adulterado e rejeitado com -32602
PASS 18 argumentos adulterados no retry nao tomam efeito
PASS 19 recusa conclui sem reservar e sem isError
PASS 20 conflito sem alternativa possivel devolve isError com a mensagem exata

FAIL 21..36: agente A2A ainda nao existe (Connection refused na 7300)
```

**20 de 36** — todo o lado MCP está fechado.

### Retry depois de reiniciar o processo (teste manual)

1. Pedido em conflito (`sala-garagem` 14h–15h) → `resultType: input_required`, chave `escolha_de_sala`, `requestState` de 507 caracteres.
2. **Matei o processo** e subi outro com a mesma `REQUEST_STATE_SECRET`.
3. Retry com o `requestState` capturado antes do restart e `action=accept`, `content.sala=sala-fusca`:

```
resultType: complete | erro: None
reserva: res-0003 | sala: sala-fusca | reservado: True | politica: 2026-11-01
```

Nada de estado em memória: o envelope selado carrega método, tool, digest dos argumentos e o payload.

### Rejeições observadas no stderr

```
requestState rejected on tools/call: seal              -> HTTP 400 (-32602)  (adulterado)
requestState rejected on tools/call: request binding   -> HTTP 400 (-32602)  (argumentos adulterados)
```

## Nota sobre determinismo do validador

As verificações 14 e 16 dependem de quais salas estão livres no intervalo. Depois do meu teste manual de restart (que criou uma reserva em `sala-fusca` 14h–15h), rodar o validador de novo no **mesmo** processo dá 19/36 e falha 14/16 por falta de alternativa — é estado em memória, não regressão. Com processo recém-iniciado: 20/36. Sempre reinicie antes de medir.

## Próxima fase

Fase 3 — agente como host MCP (`tools/list` em runtime, resource da política, headers `Mcp-*`, `traceparent`, capability de elicitation) e, na sequência, o A2A por fora e a ponte.
