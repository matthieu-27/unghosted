"""SSRF-guarded page fetch (user story 3, item 2).

Policy lives in ``unghosted.domain.ssrf`` (pure). This gateway owns the
IO: resolve DNS, check every address, then connect to a checked address —
the original hostname is only carried as SNI and Host header, so a DNS
rebinding between check and connect has no effect. Redirects are followed
manually and re-checked hop by hop. HTML content types only, size and
time capped. No JavaScript is fetched or executed.
"""

from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from unghosted.domain.ssrf import (
    FetchBlockedError,
    UrlPolicy,
    check_url,
    host_forbidden,
    resolved_ips_forbidden,
)

_MAX_REDIRECTS = 5
_ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass(frozen=True)
class FetchResult:
    text: str
    final_url: str
    content_type: str
    elapsed_ms: int


class PageFetcher(Protocol):
    async def fetch(self, url: str) -> FetchResult:
        """Fetch one page under the SSRF policy."""
        ...


class HttpPageFetcher:
    """httpx implementation. One instance per application (shares no state
    beyond configuration)."""

    def __init__(self, *, max_bytes: int, timeout_seconds: float) -> None:
        self._max_bytes = max_bytes
        self._timeout = httpx.Timeout(5.0, read=timeout_seconds)
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=False,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, url: str) -> FetchResult:
        started = time.monotonic()
        client = await self._ensure_client()
        current = url
        for _hop in range(_MAX_REDIRECTS + 1):
            split = check_url(current)
            if host_forbidden(split.host):
                raise FetchBlockedError(f"host {split.host} is a forbidden address")
            ips = await self._resolve(split.host, split.port)
            forbidden = resolved_ips_forbidden(ips)
            if forbidden:
                raise FetchBlockedError(
                    f"{split.host} resolves to forbidden address {forbidden[0]}",
                )
            pinned = ips[0]
            response = await self._request_pinned(client, split, pinned, current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location", "")
                await response.aclose()
                if not location:
                    raise FetchBlockedError("redirect without a location")
                current = _absolute(current, location)
                continue
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip()
            )
            if content_type not in _ALLOWED_CONTENT_TYPES:
                await response.aclose()
                raise FetchBlockedError(
                    f"content type {content_type!r} not allowed (HTML only)",
                )
            body = await self._read_capped(response)
            elapsed = int((time.monotonic() - started) * 1000)
            return FetchResult(
                text=body.decode("utf-8", errors="replace"),
                final_url=str(response.request.url),
                content_type=content_type,
                elapsed_ms=elapsed,
            )
        raise FetchBlockedError(f"more than {_MAX_REDIRECTS} redirects")

    async def _resolve(self, host: str, port: int) -> list[str]:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise FetchBlockedError(f"cannot resolve {host}: {exc}") from exc
        ips = list(dict.fromkeys(str(info[4][0]) for info in infos))
        if not ips:
            raise FetchBlockedError(f"{host} resolves to no address")
        return ips

    async def _request_pinned(
        self,
        client: httpx.AsyncClient,
        policy: UrlPolicy,
        ip: str,
        original_url: str,
    ) -> httpx.Response:
        """GET the original URL but connect to the pre-checked ``ip``.

        ``sni_hostname`` keeps TLS (certificate check included) against the
        real host. The Host header preserves virtual hosting. Explicit ports
        are impossible here: check_url already rejected everything but the
        scheme defaults.
        """
        request_url = httpx.URL(original_url).copy_with(host=ip)
        request = client.build_request(
            "GET",
            request_url,
            headers={"Host": policy.host},
            extensions={"sni_hostname": policy.host},
        )
        return await client.send(request, stream=True)

    async def _read_capped(self, response: httpx.Response) -> bytes:
        buffer = bytearray()
        async for chunk in response.aiter_bytes():
            buffer.extend(chunk)
            if len(buffer) > self._max_bytes:
                await response.aclose()
                raise FetchBlockedError("response exceeds the size cap")
        return bytes(buffer)


def _absolute(base: str, location: str) -> str:
    return str(httpx.URL(base).join(location))
