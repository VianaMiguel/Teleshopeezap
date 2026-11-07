"""Conexão com a API do Telegram imune a bloqueio/instabilidade de rota.

Nas redes de alguns provedores o IP que o DNS devolve para
api.telegram.org (149.154.166.110) sofre perda de pacote quase total —
o bot morre com ConnectTimeout. Outros IPs do mesmo Telegram funcionam
normalmente. Este módulo fixa a conexão em uma lista de IPs alternativos,
mantendo o SNI/certificado de api.telegram.org.

Sobrescreva a lista com TELEGRAM_API_IPS=1.2.3.4,5.6.7.8 no .env.
"""
import logging
import os

import httpx
from telegram.request import HTTPXRequest

log = logging.getLogger("ofertas.net")

HOST_API = "api.telegram.org"

IPS_PADRAO = [
    "149.154.167.99",
    "149.154.166.110",  # IP oficial do DNS — entra como último fallback
]


def _ips() -> list[str]:
    custom = os.getenv("TELEGRAM_API_IPS", "").strip()
    if custom:
        return [ip.strip() for ip in custom.split(",") if ip.strip()]
    return IPS_PADRAO


class _PinIpTransport(httpx.AsyncBaseTransport):
    """Rota api.telegram.org para IPs fixos, com fallback em caso de falha."""

    def __init__(self, ips: list[str]):
        self._ips = ips
        self._inners = [httpx.AsyncHTTPTransport() for _ in ips]

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != HOST_API:
            return await self._inners[0].handle_async_request(request)
        erros: list[Exception] = []
        for ip, inner in zip(self._ips, self._inners):
            try:
                url = request.url.copy_with(host=ip)
                req = httpx.Request(
                    request.method, url,
                    headers=dict(request.headers),
                    stream=request.stream,
                    extensions={**request.extensions, "sni_hostname": HOST_API},
                )
                return await inner.handle_async_request(req)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                log.debug("IP %s falhou (%s), tentando próximo", ip, type(e).__name__)
                erros.append(e)
        raise erros[-1]

    async def aclose(self) -> None:
        for inner in self._inners:
            await inner.aclose()


def request_telegram() -> HTTPXRequest:
    """HTTPXRequest do PTB usando a conexão com IP fixo e timeouts folgados."""
    return HTTPXRequest(
        connect_timeout=15,
        read_timeout=60,
        write_timeout=60,
        media_write_timeout=120,
        httpx_kwargs={"transport": _PinIpTransport(_ips())},
    )
