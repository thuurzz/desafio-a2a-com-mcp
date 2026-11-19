#!/usr/bin/env bash
# Sobe o servidor MCP da fase 1, roda as verificações e derruba tudo no final.
# Uso: ./scripts/testar-fase-1.sh
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

PY="$RAIZ/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "sem .venv na raiz — crie com: uv venv .venv && uv pip install --python .venv/bin/python 'mcp>=2.3,<3' && uv pip install --python .venv/bin/python -e servidor-mcp"
  exit 1
fi

PORTA="${MCP_PORT:-7301}"
BASE="http://127.0.0.1:$PORTA/mcp"
LOG="$(mktemp -t servidor-mcp.XXXXXX.log)"

cabecalhos=(
  -H "Content-Type: application/json"
  -H "Accept: application/json, text/event-stream"
  -H "MCP-Protocol-Version: 2026-07-28"
)
META='{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{"elicitation":{"form":{}}}}'

echo "== subindo servidor na porta $PORTA (log em $LOG)"
MCP_PORT="$PORTA" "$PY" servidor-mcp/main.py >"$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; wait $PID 2>/dev/null' EXIT

for _ in $(seq 1 40); do
  curl -s -o /dev/null "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: tools/list" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":0,\"method\":\"tools/list\",\"params\":{\"_meta\":$META}}" && break
  sleep 0.25
done

linha() { printf '\n\033[1m%s\033[0m\n' "$1"; }

linha "1) tools/list — deve trazer as 3 tools"
curl -s "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: tools/list" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{\"_meta\":$META}}" \
  | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print([t["name"] for t in d["result"]["tools"]])'

linha "2) _meta sem protocolVersion — deve dar HTTP 400 e code -32602"
curl -s -o /tmp/r.json -w 'HTTP %{http_code}\n' "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: tools/list" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/clientCapabilities":{}}}}'
"$PY" -c 'import json; print("code:", json.load(open("/tmp/r.json"))["error"]["code"])'

linha "3) resource politica://uso — deve trazer a versao 2026-11-01"
curl -s "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: resources/read" -H "Mcp-Name: politica://uso" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"resources/read\",\"params\":{\"uri\":\"politica://uso\",\"_meta\":$META}}" \
  | "$PY" -c 'import json,sys; c=json.load(sys.stdin)["result"]["contents"][0]; print(c["mimeType"], "|", c["text"].splitlines()[0])'

linha "4) reservar sala-aquario 09h-10h — deve reservar"
curl -s "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: tools/call" -H "Mcp-Name: reservar_sala" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"tools/call\",\"params\":{\"name\":\"reservar_sala\",\"arguments\":{\"sala\":\"sala-aquario\",\"inicio\":\"2026-11-03T09:00:00-03:00\",\"fim\":\"2026-11-03T10:00:00-03:00\",\"responsavel\":\"Arthur\"},\"_meta\":$META}}" \
  | "$PY" -c 'import json,sys; s=json.load(sys.stdin)["result"]["structuredContent"]; print(s["reserva"], s["sala"], s["reservado"], s["politica"])'

linha "5) reservar sala-garagem 14h-15h (conflita com res-0001) — fase 1 devolve erro, fase 2 vai pausar com alternativas"
curl -s "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: tools/call" -H "Mcp-Name: reservar_sala" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":5,\"method\":\"tools/call\",\"params\":{\"name\":\"reservar_sala\",\"arguments\":{\"sala\":\"sala-garagem\",\"inicio\":\"2026-11-03T14:00:00-03:00\",\"fim\":\"2026-11-03T15:00:00-03:00\",\"responsavel\":\"Marty\"},\"_meta\":$META}}" \
  | "$PY" -c 'import json,sys; r=json.load(sys.stdin)["result"]; print("isError:", r.get("isError"), "|", r["content"][0]["text"][:80])'

linha "6) política: 07h-08h — deve recusar com a mensagem exata"
curl -s "$BASE" -X POST "${cabecalhos[@]}" -H "Mcp-Method: tools/call" -H "Mcp-Name: consultar_disponibilidade" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":6,\"method\":\"tools/call\",\"params\":{\"name\":\"consultar_disponibilidade\",\"arguments\":{\"sala\":\"sala-aquario\",\"inicio\":\"2026-11-03T07:00:00-03:00\",\"fim\":\"2026-11-03T08:00:00-03:00\"},\"_meta\":$META}}" \
  | "$PY" -c 'import json,sys; r=json.load(sys.stdin)["result"]; print("isError:", r.get("isError"), "|", r["content"][0]["text"])'

linha "7) validador oficial (só as verificações de MCP; o agente A2A ainda não existe)"
"$PY" validador/validar.py --mcp "http://127.0.0.1:$PORTA" 2>/dev/null | sed -n '1,25p'

linha "8) log do stderr — método, id e traceparent por request"
grep -c 'mcp request' "$LOG" | sed 's/^/linhas de log: /'
grep -m3 'mcp request' "$LOG"
