# Roadmap do desafio — A Ponte

Fonte de verdade: `README.md` do starter (seção "Ordem de execução sugerida" e "Critérios de Aceite"),
`exemplos/wire/` e `validador/validar.py` (36 verificações).
A medida objetiva de evolução é **quantas verificações do validador passam**, agrupadas por fase.

Cada fase = 1 change OpenSpec (`openspec/changes/<id>/`) + 1 branch + commits temáticos + 1 `docs/fase-N.md`.

| Fase | Escopo | Grupo do validador | Alvo | Status |
|---|---|---|---|---|
| 1 | Servidor MCP base: 3 tools, resource da política, guard do `_meta`, log stderr | 01–12, 20 | 13 PASS | ✅ concluída |
| 2 | MRTR: `input_required`, elicitation form mode, `requestState` selado, `-32021`, retry | 13–19 | 20 PASS | ✅ concluída |
| 3 | Agente como host MCP: `tools/list` em runtime, resource, headers, `traceparent`, capability | 21–23 + log | — | ✅ concluída |
| 4 | Agente como servidor A2A: card, `SendMessage`, `GetTask`, máquina de estados da Task | 21–26, 29–31, 35 | — | ✅ concluída |
| 5 | A ponte: pausa da Task, `requestState` amarrado à Task, retry com id novo, recusa | 27–28, 32–34, 36 | 36 PASS | pendente |
| 6 | Fechamento: README de entrega, execução em clone limpo, checklist item a item | 36/36 + exit 0 | 36 PASS | pendente |

## Fase 2 — MRTR (o coração do desafio) — ✅ concluída, ver docs/fase-2.md

- Conflito em `reservar_sala` deixa de ser `isError` e passa a devolver `resultType: input_required`
  com **uma** entrada em `inputRequests` (`elicitation/create`, `mode: form`) e `requestState` opaco.
- `requestedSchema` plano: uma propriedade `sala`, `enum` com as alternativas na ordem fechada
  (capacidade crescente, empate por id) — sem alternativa, continua `isError` com
  `Sem alternativas disponiveis no intervalo`.
- `requestState` selado com `RequestStateSecurity(keys=[REQUEST_STATE_SECRET])` (AES-256-GCM do SDK),
  TTL entre 5 e 30 min, chave só em variável de ambiente (≥32 bytes). Adulterado/expirado → `-32602`.
- Cliente sem capability de elicitation form mode → `-32021` + HTTP 400 com `data.requiredCapabilities`.
- Retry: lê `inputResponses` e `requestState`, reconstrói o pedido selado (argumentos reenviados não
  mandam nada), reserva e devolve `resultType: complete`. `decline`/`cancel` → `complete` com
  `reservado: false` e `motivo`.
- Gate: PASS 13 a 19 (com 01–12 e 20 já verdes).

## Fase 3 — Agente como host MCP — ✅ concluída, ver docs/fase-3.md

- Descobre as tools por `tools/list` em runtime; nada de catálogo hardcoded.
- Lê `politica://uso` e extrai a versão da primeira linha (vai virar o campo `politica` do artifact).
- Todo request MCP carrega `_meta` completo, declara `{"elicitation": {"form": {}}}`, manda
  `MCP-Protocol-Version`, `Mcp-Method` e `Mcp-Name`.
- Propaga o `traceparent` do cliente A2A para todos os requests MCP da Task (span novo, trace-id igual).
- Gate: log do servidor MCP mostrando o `tools/list` antes do primeiro `tools/call` e o trace-id do validador.

## Fase 4 — Agente como servidor A2A — ✅ concluída, ver docs/fase-4.md

- `GET /.well-known/agent-card.json` na forma da v1.0 (`supportedInterfaces` com `protocolBinding: JSONRPC`,
  `protocolVersion: 1.0`, skill `reservar-sala`).
- `SendMessage` / `GetTask` em `/a2a`, porta 7300, JSON-RPC 2.0.
- Task com `id` e `contextId` próprios, passando por `SUBMITTED` → `WORKING` → terminal.
- Sucesso produz o artifact `reserva` com o JSON da reserva e o campo `politica`.
- Estado terminal é definitivo: `SendMessage` numa Task terminal é recusado com erro.
- Erro de execução da tool (`isError`) leva a Task para `FAILED` com a mensagem exata no histórico.
- Gate: PASS 21–26, 29–31, 35.

## Fase 5 — A ponte

- `input_required` do MCP vira `TASK_STATE_INPUT_REQUIRED`; a mensagem da Task é exatamente
  `alternativas: <ids separados por vírgula e espaço>`, na ordem do `enum`.
- `requestState` guardado no agente associado ao `taskId`, nunca exposto em card/artifact/mensagem.
- Continuação `escolha=<id>` refaz o `tools/call` com **id JSON-RPC novo** + `inputResponses` + `requestState`.
- `escolha=recusar` → `decline` → `TASK_STATE_CANCELED`. Escolha fora do `enum` mantém pausada e repete a lista.
- Estado pausado é por Task: duas pausas simultâneas não trocam `requestState`.
- Gate: PASS 27, 28, 32, 33, 34, 36 — e portanto 36/36.

## Fase 6 — Fechamento

- Substituir o `README.md` do starter pela documentação de entrega (como rodar, onde a ponte acontece,
  decisões técnicas, saída do validador).
- Rodar tudo do zero em pasta limpa, seguindo só o README.
- `dados/`, `validador/` e `exemplos/` intocados; nenhum LLM no caminho; determinismo conferido.

## Como medir o progresso

```bash
./scripts/progresso.sh      # roda o validador e agrupa PASS/FAIL por fase
```

O script imprime o total e o recorte por fase, que é o número que entra na tabela acima.
