# Fase 5 — A ponte (a nota do desafio)

Branch: `fase-5-a-ponte`. Spec: `openspec/changes/fase-5-a-ponte/`.

**36/36 com `exit=0`**, os dois processos recém-iniciados.

## A costura

- `agente/models/tarefa.py`: estado `INPUT_REQUIRED` no enum, **fora** de `ESTADOS_TERMINAIS` (pausa é retomável).
- `agente/controllers/a2a.py`:
  - `alternativas_de(pausa)` — extrai o `enum` do `requestedSchema` (fallback para `const`), puro, sem interpretar domínio.
  - tradução `Pausado → TASK_STATE_INPUT_REQUIRED` com a mensagem **exatamente** `alternativas: <id>, <id>`.
  - `_pausas[taskId]` — o `requestState` fica amarrado à Task e nunca é serializado em resposta A2A.
  - continuação `escolha=<id>` → `continuar_async` (retry com id JSON-RPC novo) → `COMPLETED` + artifact.
  - `escolha=recusar` → `CANCELED`; escolha fora do `enum` → repete a mesma linha e continua pausada.
- A profundidade MCP é a da fase 3: o agente não decide conflito, política nem alternativas.

## Evidência — validador, processos recém-iniciados

```
$ .venv/bin/python validador/validar.py --mcp http://localhost:7301 --agente http://localhost:7300
trace-id desta execucao: 51f065c7e8ace122791da1315aafa726

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
PASS 21 agent card responde 200 no well-known com JSON
PASS 22 o card declara a interface JSON-RPC com url e versao 1.0
PASS 23 o card declara a skill reservar-sala
PASS 24 SendMessage com sala livre conclui a Task
PASS 25 o artifact chama reserva e traz a versao da politica
PASS 26 GetTask devolve id, contextId e estado corrente
PASS 27 SendMessage com sala ocupada pausa a Task
PASS 28 a Task pausada lista as alternativas na ordem certa
PASS 29 escolha fora do enum mantem a Task pausada
PASS 30 a continuacao conclui a Task na sala escolhida
PASS 31 SendMessage em Task terminal e recusado
PASS 32 a recusa termina a Task em CANCELED
PASS 33 duas Tasks pausadas ao mesmo tempo concluem cada uma com a sua reserva
PASS 34 nenhuma resposta A2A carrega o requestState
PASS 35 sala inexistente termina a Task em FAILED com a mensagem da tool
PASS 36 o agente e deterministico: o mesmo pedido produz a mesma pausa

resumo: 36 passaram, 0 falharam, de 36 verificacoes

exit=0
```

## Evidência — stderr do servidor MCP

Propagação do trace-id do validador (8 requests):

```
mcp request metodo=tools/call id=40ce76fb3fdd traceparent=00-51f065c7e8ace122791da1315aafa726-b3408a05f890d904-01
mcp request metodo=tools/list id=2 traceparent=00-51f065c7e8ace122791da1315aafa726-652edfbb2b05ca8a-01
mcp request metodo=resources/read id=3 traceparent=00-51f065c7e8ace122791da1315aafa726-77144a9cf8c02420-01
```

`tools/list` antes do primeiro `tools/call`:

```
5: mcp request metodo=tools/list id=1517e75695ee
7: mcp request metodo=tools/call id=3b47e2e1934c
```

Retry com id diferente do request inicial: cada `tools/call` do agente usa id novo
(`3b47e2e1934c`, `69d7a498c3a2`, `4e368e7141c4`, ...), porque o SDK gera um id por `send_request`.

## Aviso operacional

O validador muta o estado em memória. Rodar duas vezes seguidas **no mesmo processo** derruba
verificações que dependem de salas livres (16, 24). Sempre reinicie os dois processos antes de medir —
foi assim que a execução acima deu 36/36 com exit 0.
