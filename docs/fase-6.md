# Fase 6 — Entrega

Branch: `fase-6-entrega`. Spec: `openspec/changes/fase-6-entrega/`.

## O que foi feito

`README.md` substituído pela documentação da entrega, com as quatro seções exigidas:

1. **Como rodar** — clone, `uv venv`, `uv pip install 'mcp>=2.3,<3'`, geração de `REQUEST_STATE_SECRET`,
   subida dos dois processos e execução do validador.
2. **Onde a ponte acontece** — `agente/controllers/a2a.py` (tradução `Pausado` → `TASK_STATE_INPUT_REQUIRED`
   e `_pausas[taskId]`) e `agente/views/cliente.py` (retry com `inputResponses` + `requestState` ecoado),
   com o selo/verificação em `servidor-mcp/views/app.py`.
3. **Decisões técnicas** — AES-256-GCM do SDK com TTL de 15 min e chave só em ambiente; Tasks em memória do
   agente; `ClientSession` com `allow_input_required=True`; transporte stateless com `json_response=True`;
   separação entre erro de execução (`isError`) e erro de protocolo (`error`).
4. **Saída do validador** — bloco com a execução real.

## Verificação em clone limpo

Pasta vazia, seguindo **só o README**:

```
$ git clone ~/desafio-a2a-com-mcp ~/.hermes/cache/scratch/clone-limpo
$ cd clone-limpo && uv venv .venv
$ uv pip install --python .venv/bin/python 'mcp>=2.3,<3'
$ export REQUEST_STATE_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
$ .venv/bin/python servidor-mcp/main.py &      # :7301
$ .venv/bin/python agente/servidor.py &        # :7300
$ .venv/bin/python validador/validar.py --agente http://localhost:7300 --mcp http://localhost:7301

resumo: 36 passaram, 0 falharam, de 36 verificacoes
exit=0
```

E pelo script de medição, também no clone limpo:

```
  OK Fase 1  servidor MCP base                      12/12
  OK Fase 2  MRTR (elicitation + requestState)      7/7
  OK Fase 1b conflito sem alternativa               1/1
  OK Fase 4  agente A2A (card, SendMessage, GetTask) 6/6
  OK Fase 5  a ponte (pausa, retomada, recusa)      10/10

  TOTAL: 36/36 verificações passando
  CRITÉRIO DE ACEITE ATINGIDO
```

## Checklist de entrega

- [x] `python3 validador/validar.py` passa nas 36 com os dois processos recém-iniciados e sai com 0
- [x] `dados/`, `validador/` e `exemplos/` não foram alterados
- [x] Agente determinístico, sem dependência de SDK de LLM no `pyproject.toml`
- [x] README com as quatro seções e comandos que funcionam em clone limpo
- [x] Dois processos separados; o agente fala com o MCP por HTTP
- [x] Nenhuma regra de negócio de sala no agente
- [x] `requestState` opaco para o agente, assinado (AEAD) no servidor, com TTL de 15 min
- [x] `traceparent` propagado e registrado no stderr

## Bug conhecido encontrado no caminho

O `agente/pyproject.toml` declara `packages = ["agente", ...]`, o que só faria sentido se o pacote
estivesse em `agente/agente/`. Na prática o agente roda direto do repositório (`python agente/servidor.py`
insere a raiz no `sys.path`), então a instalação editável do agente **não** é necessária nem está no
README. Fica registrado em vez de escondido.
