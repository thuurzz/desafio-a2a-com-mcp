from __future__ import annotations

import os
import socket

from mcp.server.request_state import RequestStateBoundary, RequestStateSecurity
from mcp.server.transport_security import TransportSecuritySettings

from .middleware import GuardaMetaMiddleware
from .servidor import criar_servidor as montar_servidor


def criar_servidor():
    return montar_servidor()


def _seguranca_request_state() -> RequestStateSecurity:
    """Le a chave de REQUEST_STATE_SECRET e monta a seguranca do requestState.

    A chave vem sempre do ambiente e precisa ter ao menos 32 bytes; sem ela o
    processo falha na subida, antes de escutar na porta.
    """
    segredo = os.environ.get("REQUEST_STATE_SECRET")
    if not segredo or len(segredo.encode("utf-8")) < 32:
        raise SystemExit(
            "Erro: REQUEST_STATE_SECRET ausente ou com menos de 32 bytes. "
            "Gere com: python3 -c \"import secrets; print(secrets.token_hex(32))\" "
            "e exporte antes de subir o servidor."
        )
    return RequestStateSecurity(keys=[segredo], ttl=900)


def _ips_locais() -> list[str]:
    ips = {"127.0.0.1", "localhost"}
    # socket.gethostbyname_ex costuma devolver só 127.0.1.1 quando o hostname
    # está no /etc/hosts; o truque do UDP descobre a IP da interface de saída.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        _, _, enderecos = socket.gethostbyname_ex(socket.gethostname())
        ips.update(enderecos)
    except OSError:
        pass
    extras = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    ips.update(extras)
    return sorted(ips)


def _seguranca_transporte() -> TransportSecuritySettings | None:
    """Libera o Host do bind quando o servidor escuta fora do loopback.

    O SDK aplica proteção contra DNS rebinding e devolve HTTP 421 quando o header
    Host não está na lista. Em 127.0.0.1 o default do SDK basta; com MCP_HOST=0.0.0.0
    (teste pela rede local) é preciso declarar os hosts aceitos.
    """
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    if host in {"127.0.0.1", "localhost", "::1"}:
        return None
    hosts = [f"{ip}:*" for ip in _ips_locais()] + [f"{ip}" for ip in _ips_locais()]
    origens = [f"http://{ip}:*" for ip in _ips_locais()]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origens,
    )


def criar_app(caminho: str | None = None):
    caminho = caminho or os.environ.get("MCP_PATH", "/mcp")
    servidor = montar_servidor()

    # Ciclo MRTR: sela o requestState no retorno e verifica/abre no retry.
    servidor.middleware.append(
        RequestStateBoundary(_seguranca_request_state(), default_audience="servidor-mcp")
    )

    extra = {}
    seguranca = _seguranca_transporte()
    if seguranca is not None:
        extra["transport_security"] = seguranca
    app = servidor.streamable_http_app(
        streamable_http_path=caminho,
        stateless_http=True,
        json_response=True,
        **extra,
    )
    app.add_middleware(GuardaMetaMiddleware, caminho=caminho)
    return app
