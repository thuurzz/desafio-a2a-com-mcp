# Notas do SDK mcp 2.3.0 (Python) — levantadas pelo orquestrador

Ambiente: `.venv` já criada na raiz do repo com `mcp==2.3.0` instalado.
Use SEMPRE `.venv/bin/python`. NÃO tente ler o site-packages (o sandbox bloqueia e você perde tempo).

O que NÃO existe na v2 e é comum em exemplos antigos da v1:
- `Server.call_tool()` / `@server.call_tool()` NÃO existem mais no lowlevel Server.
- `@server.list_tools()` / `@server.list_resources()` NÃO existem.

## API real do lowlevel `mcp.server.lowlevel.server.Server`

    Server(name, version=..., instructions=..., on_list_tools=..., on_call_tool=...,
           on_list_resources=..., on_read_resource=..., on_list_resource_templates=...)
    - `on_list_tools(ctx, params) -> types.ListToolsResult`
    - `on_call_tool(ctx, params) -> types.CallToolResult | types.InputRequiredResult`
    - `on_read_resource(ctx, params) -> types.ReadResourceResult | types.InputRequiredResult`
    - `Server.streamable_http_app(*, streamable_http_path="/mcp", stateless_http=..., json_response=..., transport_security=...) -> Starlette`
    - `Server.add_request_handler(method, params_type, handler)` para interceptar no nível de método.
    - `Server.middleware: list` — middleware context-tier; é AQUI que se registra o boundary de requestState.

## MRTR (o ciclo de input_required)

Resultado intermediário:
    from mcp.types import InputRequiredResult
    InputRequiredResult(result_type="input_required",
                        input_requests={"<chave do servidor>": ElicitRequestFormParams(...)},
                        request_state="<payload interno, em texto>")

Campos (confirmados no modelo): `meta`, `result_type` (Literal "input_required"), `input_requests`,
`request_state` (str | None).
    from mcp.types import ElicitRequestFormParams
    ElicitRequestFormParams(mode="form", message="...", requested_schema={...})   # schema PLANO

O retry chega no MESMO handler `on_call_tool`, com `params.input_responses` e `params.request_state`
já em texto claro (o boundary abre antes do handler). Campos de `CallToolRequestParams`:
`meta`, `input_responses`, `request_state`, `name`, `arguments`, `task`.

## requestState — o SDK já faz o trabalho pesado

    from mcp.server.request_state import RequestStateSecurity, RequestStateBoundary

    security = RequestStateSecurity(keys=[os.environ["REQUEST_STATE_SECRET"]], ttl=900)
    servidor.middleware.append(RequestStateBoundary(security, default_audience="servidor-mcp"))

Fatos verificados no código instalado:
- `RequestStateSecurity(keys=[...])` usa AES-256-GCM por dentro (`AESGCMRequestStateCodec`), deriva com
  HKDF-SHA256, exige chave de **>= 32 bytes** (levanta ValueError se menor). `keys[0]` sela, todas abrem.
  `ttl` é em segundos e precisa ser positivo — use 900 (15 min), dentro da faixa 5–30 min pedida.
- O boundary sela o `request_state` que o handler devolver e, no retry, **verifica e abre** antes do handler.
  Ele NÃO guarda nada em memória: o envelope carrega `v, iat, exp, m, t, a, s` (método, target, digest dos
  argumentos, payload). Por isso o retry funciona depois de reiniciar o processo.
- Token adulterado, expirado, de outro método ou com **argumentos diferentes** é rejeitado com `-32602`
  ("Invalid or expired requestState"). Ou seja: o requisito "argumento adulterado não pode tomar efeito" e o
  "outro método" já vêm de graça — só não atrapalhe. O handler nunca chama o codec.
- O handler recebe `params["request_state"]` como o **texto que ele mesmo devolveu** (JSON serializado),
  então guarde ali o pedido original (sala, inicio, fim, responsavel) e as alternativas.

## Capability de elicitation (erro -32021)

Confirmado em execução, em modo stateless: `ctx.session.client_capabilities` reflete o `_meta` DO REQUEST.
    caps = ctx.session.client_capabilities
    tem_form = bool(caps and caps.elicitation and caps.elicitation.form)

Para recusar:
    from mcp.server.mcpserver.server import require_client_extension   # só serve para extensions
    # caminho direto, que é o que precisamos:
    from mcp.server.lowlevel.server import MISSING_REQUIRED_CLIENT_CAPABILITY  # -32021
    from mcp.types import MissingRequiredClientCapabilityErrorData, ClientCapabilities
    raise MCPError(code=MISSING_REQUIRED_CLIENT_CAPABILITY,
                   message="Client did not declare elicitation capability in form mode",
                   data=MissingRequiredClientCapabilityErrorData(
                       required_capabilities=ClientCapabilities(
                           elicitation={"form": {}})).model_dump(by_alias=True, mode="json", exclude_none=True))

O `data` serializa como `requiredCapabilities`, que é o que o validador procura.
Se o nome do import do código não existir nessa versão, procure com:
    .venv/bin/python -c "import mcp; from mcp.server.lowlevel import server as s; print([n for n in dir(s) if 'CAPAB' in n.upper() or 'MCPError' in n])"

**HTTP 400**: o status não é decidido pelo MCPError. O `GuardaMetaMiddleware` (ASGI) já força 400 nos casos
de `_meta`; para `-32021` e `-32602` o caminho é o middleware interceptar o `http.response.start`,
bufferizar o corpo e reescrever o status para 400 quando o JSON-RPC trouxer `error.code` nesses valores.

## Elicitation (helpers opcionais)

    mcp.server.elicitation: elicit_with_validation, AcceptedElicitation, DeclinedElicitation,
    CancelledElicitation, render_elicitation_schema
São para o lado CLIENTE/host (quem responde). O servidor só devolve `InputRequiredResult`.

## Tipos de wire

`mcp.types`: `CallToolResult`, `TextContent`, `StructuredContent`, `InputRequiredResult`,
`InputResponses`, `ElicitRequestFormParams`, `ListToolsResult`, `Tool`, `ReadResourceResult`,
`TextResourceContents`, `MissingRequiredClientCapabilityErrorData`, `ClientCapabilities`.

Antes de escrever código, confirme cada assinatura com:
    .venv/bin/python -c "import inspect, mcp.types as t; print([n for n in dir(t) if 'Input' in n or 'Structured' in n])"
