# Tasks

## 1. README de entrega (~60 min)

- [x] 1.1 Escrever as quatro seções exigidas: como rodar, onde a ponte acontece, decisões técnicas e saída do validador. **Verificação:** `grep -c '^## ' README.md` mostra as seções, e os comandos citados existem no repositório.
- [x] 1.2 Incluir a geração/exportação de `REQUEST_STATE_SECRET` sem fixar valor. **Verificação:** `grep -n 'secrets.token_hex(32)' README.md` encontra o comando e `grep -c 'REQUEST_STATE_SECRET=' README.md` não mostra valor literal.

## 2. Verificação em clone limpo (~40 min)

- [x] 2.1 Clonar o repositório em pasta vazia, seguir só o README e rodar o validador com os dois processos. **Verificação:** `git clone ... && uv venv .venv && uv pip install ... && export REQUEST_STATE_SECRET=... && (.venv/bin/python servidor-mcp/main.py &) && (.venv/bin/python agente/servidor.py &) && .venv/bin/python validador/validar.py` termina com `resumo: 36 passaram, 0 falharam` e `exit=0`.
- [x] 2.2 Conferir que `dados/`, `validador/` e `exemplos/` não foram alterados. **Verificação:** `git diff --stat origin/main -- dados validador exemplos` sem saída.

## 3. Fechamento do roadmap (~20 min)

- [x] 3.1 Marcar as seis fases em `docs/roadmap.md` e registrar a saída final em `docs/fase-6.md`. **Verificação:** `grep -c '✅ concluída' docs/roadmap.md` é 5 (as fases 1 a 5) e a fase 6 consta como entrega.
