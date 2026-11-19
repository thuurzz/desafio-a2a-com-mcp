# Auditoria dos Critérios de Aceite (antes do merge)

Fonte: `## Critérios de Aceite` do README do starter (`origin/main`). Todos obrigatórios.
Data da auditoria: 18/11/2026, branch `fase-6-entrega`, dois processos recém-iniciados.

## Como foi verificado

| Instrumento | O que cobre |
|---|---|
| `validador/validar.py` (36 verificações) | quase todos os itens técnicos, em HTTP direto e A2A |
| Fluxo do avaliador, passos 3 a 13 | roteiro manual do enunciado, reproduzido por script |
| Inspeção do repo | estrutura, `.gitignore`, dependências, ausência de regra de negócio no agente |

## Servidor MCP

- [x] Sobe na `7301` em Streamable HTTP e responde `tools/list` com as três tools → PASS 01, 02
- [x] Toda tool tem `inputSchema` que é objeto JSON Schema válido → PASS 02
- [x] `listar_salas` devolve `structuredContent` conforme o `outputSchema` e o mesmo JSON em texto → PASS 03
- [x] Request sem `protocolVersion` ou sem `clientCapabilities` → `-32602` + HTTP 400 → PASS 04, 05
- [x] `tools/call` de tool inexistente é recusado → PASS 06
- [x] `resources/read` de `politica://uso` devolve a política; URI inexistente → `-32602` → PASS 07, 08
- [x] Sala inexistente, janela, duração e intervalo invertido → `isError` com mensagens exatas → PASS 09 a 12
- [x] stderr registra método, id e `traceparent` de cada request → linhas `mcp request metodo=… id=… traceparent=…`

## MRTR

- [x] Conflito → `resultType: input_required`, uma entrada em `inputRequests`, form mode, `requestState` → PASS 13
- [x] `requestedSchema` plano, restrito às alternativas, na ordem definida → PASS 14
- [x] Sem capability de elicitation → `-32021` com `data.requiredCapabilities` e HTTP 400 → PASS 15
- [x] Retry com `inputResponses` + `requestState` conclui com `resultType: complete` → PASS 16
- [x] `requestState` adulterado → `-32602` → PASS 17
- [x] Retry com argumentos adulterados não toma efeito (o estado selado vence) → PASS 18
- [x] Retry válido conclui mesmo com restart do servidor MCP no meio → **verificado à mão**:
  conflito (507 chars de estado) → `kill` do processo → subir de novo com a mesma chave → retry:
  `resultType: complete | res-0003 | sala-mirante | reservado: True | politica: 2026-11-01`
- [x] Chave de integridade vem de `REQUEST_STATE_SECRET` com ≥ 32 bytes, sem segredo no código →
  `servidor-mcp/views/app.py:23` lê de `os.environ`; sem a variável o processo sai com `exit=1` (reproduzido)
- [x] `action: decline` conclui sem reservar e sem `isError` → PASS 19

## Agente como host MCP

- [x] Log mostra `tools/list` antes do primeiro `tools/call` → `grep -n`: `tools/list` na linha 7, primeiro
  `tools/call` na linha 11
- [x] Log mostra o `traceparent` com o mesmo trace-id enviado no header A2A → 4 requests com o trace-id
  `812abf80face7a273a9a75163d5262e3`
- [x] Os requests do agente declaram elicitation em form mode → `_meta.clientCapabilities` com
  `{"elicitation": {"form": {}}}` em `agente/views/cliente.py`

## Agente como servidor A2A

- [x] `GET /.well-known/agent-card.json` responde 200 com card v1.0 → fluxo passo 3, comparado com `exemplos/wire/07`
- [x] Card declara interface JSON-RPC, URL do endpoint, versão `1.0` e skill `reservar-sala` → PASS 22, 23
- [x] `SendMessage` com sala livre termina em `COMPLETED` com artifact `reserva` → PASS 24
- [x] Artifact traz a reserva criada e o campo `politica` lido do resource → PASS 25
- [x] `GetTask` devolve `id`, `contextId`, estado corrente e artifact → PASS 26
- [x] `SendMessage` em Task terminal é recusado com erro → PASS 31
- [x] Sala inexistente → `TASK_STATE_FAILED` com a mensagem exata no histórico → PASS 35 e fluxo passo 10
  (`Sala inexistente: sala-inexistente`)

## A ponte

- [x] Sala ocupada → `TASK_STATE_INPUT_REQUIRED` com `alternativas: sala-fusca, sala-mirante` → PASS 27, 28
- [x] `escolha=<id>` conclui em `COMPLETED` na sala escolhida → PASS 30 e fluxo passo 8
- [x] `escolha=recusar` termina em `TASK_STATE_CANCELED` → PASS 32 e fluxo passo 9
- [x] Escolha fora do `enum` mantém `INPUT_REQUIRED` → PASS 29
- [x] Duas Tasks pausadas ao mesmo tempo não trocam `requestState` → PASS 33
- [x] `requestState` não aparece em nenhuma resposta A2A → PASS 34

## Validação e entrega

- [x] `python3 validador/validar.py` passa nas 36 com processos novos e sai com 0 → `36/36`, `exit=0`
- [x] `dados/`, `validador/` e `exemplos/` não foram alterados → `git diff --stat origin/main` vazio para os três
- [x] Agente determinístico, sem SDK de LLM → PASS 36; `grep` de openai/anthropic/litellm/langchain/ollama
  nos `pyproject.toml` não encontra nada
- [x] README tem as quatro seções e os comandos funcionam em clone limpo → clone verificado, `36/36`
- [x] Estrutura obrigatória do entregável preservada (`README.md`, `dados/`, `validador/`, `exemplos/`,
  `servidor-mcp/`, `agente/`)

## Ajustes feitos nesta auditoria

- **Versões travadas:** `mcp>=2.3,<3` virou `mcp==2.3.0` nos dois `pyproject.toml` e nos comandos do README.
  O enunciado pede "versões travadas" — faixa não é travamento.
- **Script do fluxo do avaliador** (execução temporária, não versionada aqui) reproduziu os passos 3 e 7 a 13:
  8/8 passaram. O passo 13 exigiu ocupar um horário novo, porque a execução sequencial já tinha consumido
  as alternativas das 14h — comportamento de estado em memória, não falha.

## Ressalva honesta

Dois itens não são cobertos por assert automático e foram conferidos por inspeção, não por teste:

1. **`traceparent` do header A2A** (critério do host MCP): verifiquei que os requests do agente saem com o
   mesmo trace-id em `tools/list`, `resources/read` e `tools/call`. O handshake `server/discover` do SDK
   não aceita `_meta` e sai sem `traceparent` — é negociação de conexão, não tráfego da Task, e está
   documentado em `docs/fase-3.md`.
2. **"O agente não implementa regra de negócio"**: verificado por leitura de `agente/controllers/a2a.py`
   (só traduz protocolo), não por teste automatizado — o validador não checa isso.
