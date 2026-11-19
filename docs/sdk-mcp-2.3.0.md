# Notas do SDK mcp 2.3.0 (Python) — levantadas pelo orquestrador

Ambiente: `.venv` já criada na raiz do repo com `mcp==2.3.0` instalado.
Use SEMPRE `.venv/bin/python`. NÃO tente ler o site-packages (sandbox bloqueia).

O que NÃO existe na v2 e é comum em exemplos antigos da v1:
- `Server.call_tool()` / `@server.call_tool()` NÃO existem mais no lowlevel Server.
- `@server.list_tools()` / `@server.list_resources()` NÃO existem.

API real do lowlevel `mcp.server.lowlevel.server.Server`:
    Server(name, version=..., instructions=..., on_list_tools=..., on_call_tool=...,
           on_list_resources=..., on_read_resource=..., on_list_resource_templates=...)
    - `on_list_tools(ctx, params) -> types.ListToolsResult`
    - `on_call_tool(ctx, params) -> types.CallToolResult | types.InputRequiredResult`
    - `on_read_resource(ctx, params) -> types.ReadResourceResult | types.InputRequiredResult`
    - `Server.streamable_http_app(*, streamable_http_path="/mcp", stateless_http=..., json_response=..., host=...) -> Starlette`
    - `Server.add_request_handler(method, params_type, handler)` para interceptar no nível de método (útil para rejeitar _meta ausente antes do handler).

MRTR vem de fábrica: mcp.server.request_state
    - `RequestStateSecurity(keys=[secreto])` -> AES-256-GCM (AEAD) embutido, `ttl` em segundos (default 600 = 10 min)
    - `RequestStateBoundary(security, default_audience=...)` é o middleware que sela/verifica o `requestState`
      e responde `-32602` com "Invalid or expired requestState" quando falha.
    - `from mcp.server.request_state import RequestStateSecurity, RequestStateBoundary, is_input_required`
    - o handler que devolve `input_required` NÃO chama o codec: devolve `types.InputRequiredResult` com
      `inputRequests` + o payload interno; o boundary sela.
- Elicitation: `mcp.server.elicitation` (`elicit_with_validation`, `AcceptedElicitation`,
  `DeclinedElicitation`, `CancelledElicitation`, `render_elicitation_schema`).
- Tipos de wire: `mcp.types` (`CallToolResult`, `TextContent`, `StructuredContent`, `InputRequiredResult`,
  `ListToolsResult`, `Tool`, `ReadResourceResult`, `TextResourceContents`).

Antes de escrever código, confirme cada assinatura com:
    .venv/bin/python -c "import inspect, mcp.types as t; print([n for n in dir(t) if 'Input' in n or 'Structured' in n])"
