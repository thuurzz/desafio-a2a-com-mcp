# Fase 6 — Entrega

Branch: `fase-6-entrega`. Spec: `openspec/changes/fase-6-entrega/`.

## O que foi feito

`README.md` substituído pela documentação da entrega, com as quatro seções exigidas:

1. **Como rodar** — clone, `uv venv`, `uv pip install 'mcp==2.3.0'`, geração de `REQUEST_STATE_SECRET`,
   subida dos dois processos e execução do validador.
2. **Onde a ponte acontece** — `agente/controllers/a2a.py` (tradução `Pausado` → `TASK_STATE_INPUT_REQUIRED`
   e `_pausas[taskId]`) e `agente/views/cliente.py` (retry com `inputResponses` + `requestState` ecoado),
   com o selo/verificação em `servidor-mcp/views/app.py`.
3. **Decisões técnicas** — AES-256-GCM do SDK com TTL de 15 min e chave só em ambiente; Tasks em memória do
   agente; `ClientSession` com `allow_input_required=True`; transporte stateless com `json_response=True`;
   separação entre erro de execução (`isError`) e erro de protocolo (`error`).
4. **Saída do validador** — bloco com a execução real.

## Verificação em clone limpo (após a revisão do Arthur)

Pasta vazia, seguindo **só o README** — com os dois processos em terminais separados, cada um com o
seu próprio `export` (foi o furo que o Arthur apontou: um `export` não atravessa terminais):

```
$ git clone ~/desafio-a2a-com-mcp ~/.hermes/cache/scratch/clone2 && cd clone2
$ uv venv .venv
$ uv pip install --python .venv/bin/python 'mcp==2.3.0'
$ uv pip install --python .venv/bin/python -e agente
$ python3 -c 'import secrets; print(secrets.token_hex(32))' > .request_state_secret && chmod 600 .request_state_secret

# terminal 1
$ export REQUEST_STATE_SECRET="$(cat .request_state_secret)" && .venv/bin/python servidor-mcp/main.py
# terminal 2
$ export REQUEST_STATE_SECRET="$(cat .request_state_secret)" && .venv/bin/python agente/servidor.py

# terminal 3
$ .venv/bin/python validador/validar.py --agente http://localhost:7300 --mcp http://localhost:7301

resumo: 36 passaram, 0 falharam, de 36 verificacoes
exit=0
```

O cenário do erro também foi reproduzido de propósito:

```
$ env -u REQUEST_STATE_SECRET .venv/bin/python servidor-mcp/main.py
Erro: REQUEST_STATE_SECRET ausente ou com menos de 32 bytes. Gere com: python3 -c "import secrets; print(secrets.token_hex(32))" e exporte antes de subir o servidor.
exit=1
```

## Bug corrigido nesta fase

`agente/pyproject.toml` declarava `packages = ["agente", "agente.models", "agente.controllers", "agente.views"]`,
mas o código mora em `agente/models/`, `agente/controllers/` e `agente/views/` — ou seja, `pip install -e agente`
instalaria um pacote sem módulos. Corrigido para `packages = ["models", "controllers", "views"]`, com
`uv pip install -e agente` documentado no README e verificado em clone limpo (instala `agente-a2a-salas==0.1.0`).

## Checklist de entrega

- [x] `python3 validador/validar.py` passa nas 36 com os dois processos recém-iniciados e sai com 0
- [x] `dados/`, `validador/` e `exemplos/` não foram alterados
- [x] Agente determinístico, sem dependência de SDK de LLM no `pyproject.toml`
- [x] README com as quatro seções e comandos que funcionam em clone limpo
- [x] Dois processos separados; o agente fala com o MCP por HTTP
- [x] Nenhuma regra de negócio de sala no agente
- [x] `requestState` opaco para o agente, assinado (AEAD) no servidor, com TTL de 15 min
- [x] `traceparent` propagado e registrado no stderr
