#!/usr/bin/env bash
# Mede o progresso: roda o validador e agrupa as 36 verificações por fase do roadmap.
# Uso: ./scripts/progresso.sh [porta-mcp] [porta-agente]
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

PY="$RAIZ/.venv/bin/python"
[ -x "$PY" ] || { echo "sem .venv na raiz (veja docs/fase-1.md)"; exit 1; }

PORTA_MCP="${1:-${MCP_PORT:-7301}}"
PORTA_AGENTE="${2:-${AGENTE_PORT:-7300}}"

SAIDA="$(mktemp -t validador.XXXXXX.txt)"
if ss -tln 2>/dev/null | grep -q ":$PORTA_MCP "; then
  echo "aviso: já existe processo na porta $PORTA_MCP; o validador assume processos recém-iniciados,"
  echo "       então o resultado pode variar se as reservas em memória já foram mexidas."
fi
"$PY" validador/validar.py --mcp "http://127.0.0.1:$PORTA_MCP" --agente "http://127.0.0.1:$PORTA_AGENTE" >"$SAIDA" 2>&1
CODIGO=$?

"$PY" - "$SAIDA" <<'PY'
import re, sys, pathlib

texto = pathlib.Path(sys.argv[1]).read_text()
linhas = re.findall(r"^(PASS|FAIL) (\d{2}) (.*)$", texto, re.M)
resultado = {int(n): (s == "PASS", d) for s, n, d in linhas}

fases = [
    ("Fase 1  servidor MCP base", range(1, 13)),
    ("Fase 2  MRTR (elicitation + requestState)", range(13, 20)),
    ("Fase 1b conflito sem alternativa", [20]),
    ("Fase 4  agente A2A (card, SendMessage, GetTask)", range(21, 27)),
    ("Fase 5  a ponte (pausa, retomada, recusa)", range(27, 37)),
]

total_pass = sum(1 for ok, _ in resultado.values() if ok)
print()
for nome, faixa in fases:
    do_grupo = [(n, resultado[n]) for n in faixa if n in resultado]
    if not do_grupo:
        continue
    p = sum(1 for _, (ok, _) in do_grupo if ok)
    marca = "OK " if p == len(do_grupo) else "   "
    print(f"  {marca}{nome:<46} {p}/{len(do_grupo)}")
    for n, (ok, desc) in do_grupo:
        if not ok:
            print(f"        FAIL {n:02d} {desc}")

print()
print(f"  TOTAL: {total_pass}/36 verificações passando")
print(f"  {'CRITÉRIO DE ACEITE ATINGIDO' if total_pass == 36 else 'ainda não é o aceite final (36/36)'}")
PY

rm -f "$SAIDA"
exit $CODIGO
