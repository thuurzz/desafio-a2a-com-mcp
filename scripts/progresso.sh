#!/usr/bin/env bash
# Mede o progresso: sobe os DOIS processos do zero em portas isoladas, roda o validador
# e agrupa as 36 verificações por fase do roadmap. Derruba tudo no fim.
# Uso: ./scripts/progresso.sh [porta-mcp] [porta-agente]
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

PY="$RAIZ/.venv/bin/python"
[ -x "$PY" ] || { echo "sem .venv na raiz (veja docs/fase-1.md)"; exit 1; }

# Portas isoladas por default, para não brigar com instâncias já abertas
# e garantir que a medição use processos recém-iniciados.
PORTA_MCP="${1:-${MCP_PORT:-7391}}"
PORTA_AGENTE="${2:-${AGENTE_PORT:-7390}}"

LOG_MCP="$(mktemp -t mcp-progresso.XXXXXX.log)"
LOG_AGENTE="$(mktemp -t agente-progresso.XXXXXX.log)"
SAIDA="$(mktemp -t validador.XXXXXX.txt)"

export REQUEST_STATE_SECRET="${REQUEST_STATE_SECRET:-$("$PY" -c 'import secrets;print(secrets.token_hex(32))')}"
export MCP_PORT="$PORTA_MCP"
export A2A_PORT="$PORTA_AGENTE"
# O agente precisa falar com o servidor DESTA execução, não com o default 7301.
export MCP_URL="http://127.0.0.1:$PORTA_MCP/mcp"

echo "subindo servidor MCP em :$PORTA_MCP e agente A2A em :$PORTA_AGENTE (processos novos)"
"$PY" servidor-mcp/main.py >"$LOG_MCP" 2>&1 &
PID_MCP=$!
"$PY" agente/servidor.py >"$LOG_AGENTE" 2>&1 &
PID_AGENTE=$!
trap 'kill $PID_MCP $PID_AGENTE 2>/dev/null; wait $PID_MCP $PID_AGENTE 2>/dev/null' EXIT

for _ in $(seq 1 60); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORTA_MCP/mcp" -X POST \
      -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
      -H 'MCP-Protocol-Version: 2026-07-28' -H 'Mcp-Method: tools/list' \
      -d '{"jsonrpc":"2.0","id":0,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{"elicitation":{"form":{}}}}}}' \
     && curl -s -o /dev/null "http://127.0.0.1:$PORTA_AGENTE/.well-known/agent-card.json"; then
    break
  fi
  sleep 0.25
done

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
