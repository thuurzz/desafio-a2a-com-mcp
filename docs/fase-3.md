# Fase 3 — Agente como host MCP

Branch: `fase-3-agente-host-mcp`. Spec: `openspec/changes/fase-3-agente-host-mcp/`.
Implementação delegada ao Claude Code (`deepseek-v4-pro` via proxy LiteLLM).

## O que existe agora

`agente/`, processo separado do servidor MCP, layout `models/ controllers/ views/`:

- `views/cliente.py` — cliente MCP com o **SDK oficial**: `streamable_http_client` + `ClientSession`.
  O ponto central é `call_tool(..., allow_input_required=True)`, que devolve o `InputRequiredResult`
  **cru** em vez de deixar o driver de MRTR do SDK responder sozinho.
- `controllers/parser.py` — pedido fixo interpretado por regex, sem LLM.
- `controllers/orquestrador.py` — `descobrir`, `executar_pedido`, `continuar`; traduz o resultado em
  `Completado | Pausado | Falhou`.
- `models/pedido.py` — `Pedido` e os três resultados. `Pausado` guarda `input_requests` e `request_state`
  opacos (a única leitura é a chave única, exigida para o eco do retry).
- `main.py` — exercita o ciclo completo (livre → conflito → aceite → recusa).

## Evidência 1 — o ciclo roda

```
tools: ['listar_salas', 'consultar_disponibilidade', 'reservar_sala']
politica: 2026-11-01
reserva livre -> completado(reservado=True, sala=sala-porao, politica=2026-11-01)
reserva em conflito -> pausado(chaves=['escolha_de_sala'])
continuar(sala-fusca) -> completado(reservado=True, sala=sala-fusca, politica=2026-11-01)
reserva recusavel -> pausado(chaves=['escolha_de_sala'])
continuar(recusar) -> completado(reservado=False, sala=None, politica=2026-11-01)
```

A versão da política vem do **resource**, não do `structuredContent` da tool.

## Evidência 2 — headers que o transporte espelha do corpo

Medido com um proxy que loga os headers e repassa para o servidor real:

```
REQ metodo=tools/list       mcp-method=tools/list       mcp-name=-                 mcp-protocol-version=2026-07-28
REQ metodo=resources/read   mcp-method=resources/read   mcp-name=politica://uso    mcp-protocol-version=2026-07-28
REQ metodo=tools/call       mcp-method=tools/call       mcp-name=reservar_sala     mcp-protocol-version=2026-07-28
```

O SDK monta `Mcp-Method`, `Mcp-Name` (tool em `tools/call`, URI em `resources/read`) e
`MCP-Protocol-Version` a partir do corpo — não foi preciso transporte fino nem gambiarra.

## Evidência 3 — `tools/list` antes do primeiro `tools/call`

```
mcp request metodo=server/discover id=1
mcp request metodo=tools/list      id=2   <- descoberta em runtime
mcp request metodo=resources/read  id=3   <- versão da política
mcp request metodo=tools/call      id=4   <- primeira tool
```

## Evidência 4 — `traceparent` propagado

Chamada com `--traceparent 00-4bf92f3577b34da6a3ce929d0e0e4736-...`:

```
mcp request metodo=tools/list      id=2 traceparent=00-4bf92f3577b34da6a3ce929d0e0e4736-c082cfcb66c7c598-01
mcp request metodo=resources/read  id=3 traceparent=00-4bf92f3577b34da6a3ce929d0e0e4736-35dda37d0330e5e9-01
mcp request metodo=tools/call      id=4 traceparent=00-4bf92f3577b34da6a3ce929d0e0e4736-4ed83ee6b113480a-01
```

Trace-id preservado, span-id novo por request, exatamente como o enunciado pede.
Exceção conhecida: o `server/discover` (handshake do SDK) não aceita `meta` — ver "Limitações".

## Validador

20/36 — os 20 do lado MCP continuam verdes; 21–36 dependem do servidor A2A (fase 4) e da ponte (fase 5).

## Limitações registradas

- `ClientSession.discover()` não aceita `meta`, então o handshake `server/discover` vai sem `traceparent`.
  É negociação de conexão, não tráfego da Task: `tools/list`, `resources/read`, `tools/call` e o retry
  carregam o trace-id. Documentado aqui em vez de contornar reescrevendo o protocolo.
- Cada operação abre um `ClientSession` novo (o enunciado permite manter o cliente vivo, não obriga).
  Custo: um `server/discover` por operação no stderr.
