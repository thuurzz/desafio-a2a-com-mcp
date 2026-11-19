## Correção: MCP fora do ar devolvia HTTP 500

O diagnóstico veio do feedback da avaliação, e está correto. Reproduzi e corrigi.

### O que acontecia

Com o servidor MCP fora do ar, `SendMessage` devolvia **HTTP 500** (`Internal Server Error`) em vez de
terminar a Task em `TASK_STATE_FAILED`.

Reprodução (agente no ar, MCP derrubado):

```
$ curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:7300/a2a -d @send.json
500
```

O traceback real mostra a origem:

```
File ".../mcp/client/session.py", line 777, in discover
    raw = await self.send_discover(LATEST_MODERN_VERSION)
  ...
asyncio.exceptions.CancelledError: Cancelled via cancel scope 712cb4bea990
```

Por baixo, a causa raiz é `httpx2.ConnectError: All connection attempts failed`, engolida pelo teardown
do task group do SDK.

### Por que escapava

`streamable_http_client` roda o POST dentro de um `anyio.create_task_group()`. Quando a conexão falha,
o grupo cancela as tasks irmãs — inclusive a que aguardava a resposta no `memory` stream. O que chega no
ponto do `await` é `CancelledError`, **não** o `ConnectError`.

Em Python, `asyncio.CancelledError` herda de `BaseException`, não de `Exception`. O `except Exception`
que existia em `agente/controllers/a2a.py` (com o comentário `# malformado, MCP fora, etc.`) nunca
disparava, e o handler morria antes de montar o status da Task.

### A correção

`_falar_com_mcp`, um invólucro usado pelos **dois** caminhos que falam com o MCP — abertura
(`_abrir_e_executar`) e continuação de pausa (`_continuar`):

```python
async def _falar_com_mcp(espera: Any) -> Resultado:
    try:
        return await espera
    except asyncio.CancelledError:
        _absorver_cancelamento()
        return Falhou(mensagem=MENSAGEM_MCP_INDISPONIVEL)
    except Exception as exc:
        return Falhou(mensagem=str(exc))
```

`_absorver_cancelamento()` chama `Task.uncancel()` até zerar o contador de cancelamento. Sem isso, o
cancelamento já entregue voltaria a levantar no próximo `await` do handler. Absorver é seguro aqui
porque o código que segue é **síncrono** — nada mais é aguardado até o fim do handler.

A mensagem é fixa (`MCP indisponivel: nao foi possivel concluir a reserva (falha de conexao com o
servidor MCP)`), não o texto da exceção de biblioteca, que variaria entre versões e quebraria a
estabilidade da resposta da Task.

### Verificação

| Cenário | Antes | Depois |
|---|---|---|
| `SendMessage` com o MCP fora | HTTP 500, corpo `Internal Server Error` | HTTP 200, `TASK_STATE_FAILED`, mensagem `MCP indisponivel: ...` |
| Quatro `SendMessage` seguidos com o MCP fora | 500 em todos | 200 + `FAILED` em todos (nenhum estado de cancelamento residual) |
| `escolha=...` de Task pausada com o MCP fora | HTTP 500 | HTTP 200, `TASK_STATE_FAILED` |
| `./scripts/progresso.sh` | 36/36 | **36/36** |
| Fluxo do avaliador (passos 3 e 7 a 13) | 8/8 | **8/8** |

Com o MCP no ar, nada mudou: o caminho feliz não toca o `except`.

### Sobra conhecida (não afeta a resposta)

Ao derrubar o MCP, o teardown do gerador do SDK ainda registra no log:

```
Task exception was never retrieved
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

É a finalização interna do gerador `streamable_http_client` rodando em outra task. Acontece **depois**
que a resposta já foi enviada, não muda o status HTTP nem o estado da Task, e a origem está no SDK — não
no agente. Vale saber que existe para não confundir com erro do projeto ao ler o log.
