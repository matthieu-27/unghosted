"""Fetch gateway: IP pinning, redirects, content type, size cap.

The httpx transport is mocked and DNS resolution monkeypatched, so the
SSRF policy is exercised without any network. The transport handler
asserts the connection actually targets the checked IP (us-7 item 2).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from unghosted.domain.ssrf import FetchBlockedError
from unghosted.gateways.fetch import HttpPageFetcher

PUBLIC_IP = "93.184.216.34"


def make_fetcher(
    handler: Any,
    *,
    resolve_to: list[str] | None = None,
    max_bytes: int = 2_097_152,
) -> HttpPageFetcher:
    fetcher = HttpPageFetcher(max_bytes=max_bytes, timeout_seconds=15.0)
    fetcher._ensure_client = lambda: _patched_client(handler)  # type: ignore[method-assign]
    if resolve_to is not None:

        async def fake_resolve(host: str, port: int) -> list[str]:
            return resolve_to

        fetcher._resolve = fake_resolve  # type: ignore[method-assign]
    return fetcher


async def _patched_client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(5.0, read=15.0),
        transport=httpx.MockTransport(handler),
    )


def ok_handler(expected_ip: str = PUBLIC_IP) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == expected_ip, "connection not pinned to checked IP"
        assert request.headers["host"] == "example.com"
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><body>ok</body></html>",
        )

    return handler


async def test_fetch_pins_connection_to_resolved_ip() -> None:
    fetcher = make_fetcher(ok_handler(), resolve_to=[PUBLIC_IP])
    result = await fetcher.fetch("https://example.com/page")
    assert result.text == "<html><body>ok</body></html>"
    assert result.content_type == "text/html"
    await fetcher.close()


async def test_fetch_blocked_when_resolution_hits_private_range() -> None:
    fetcher = make_fetcher(ok_handler(), resolve_to=["93.184.216.34", "10.0.0.9"])
    with pytest.raises(FetchBlockedError, match="forbidden address"):
        await fetcher.fetch("https://example.com/page")
    await fetcher.close()


async def test_fetch_blocked_on_metadata_ip() -> None:
    fetcher = make_fetcher(ok_handler(), resolve_to=["169.254.169.254"])
    with pytest.raises(FetchBlockedError, match="forbidden address"):
        await fetcher.fetch("https://example.com/page")
    await fetcher.close()


async def test_fetch_blocked_on_literal_ip_host() -> None:
    fetcher = make_fetcher(ok_handler())
    with pytest.raises(FetchBlockedError, match="forbidden"):
        await fetcher.fetch("http://127.0.0.1/")
    await fetcher.close()


async def test_fetch_rechecks_each_redirect_hop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "http://10.0.0.5/inside"})
        return httpx.Response(200, text="<html></html>")

    fetcher = make_fetcher(handler, resolve_to=[PUBLIC_IP])
    with pytest.raises(FetchBlockedError, match="forbidden"):
        await fetcher.fetch("https://example.com/start")
    await fetcher.close()


async def test_fetch_follows_safe_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(
                301, headers={"location": "https://other.example/final"}
            )
        assert request.headers["host"] == "other.example"
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html>final</html>",
        )

    fetcher = make_fetcher(handler, resolve_to=[PUBLIC_IP])
    result = await fetcher.fetch("https://example.com/start")
    assert result.text == "<html>final</html>"
    await fetcher.close()


async def test_fetch_redirect_loop_capped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/loop"})

    fetcher = make_fetcher(handler, resolve_to=[PUBLIC_IP])
    with pytest.raises(FetchBlockedError, match="redirects"):
        await fetcher.fetch("https://example.com/loop")
    await fetcher.close()


async def test_fetch_rejects_non_html_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"})

    fetcher = make_fetcher(handler, resolve_to=[PUBLIC_IP])
    with pytest.raises(FetchBlockedError, match="content type"):
        await fetcher.fetch("https://example.com/api")
    await fetcher.close()


async def test_fetch_enforces_size_cap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"x" * 100,
        )

    fetcher = make_fetcher(handler, resolve_to=[PUBLIC_IP], max_bytes=50)
    with pytest.raises(FetchBlockedError, match="size cap"):
        await fetcher.fetch("https://example.com/big")
    await fetcher.close()


async def test_fetch_rejects_non_default_port() -> None:
    fetcher = make_fetcher(ok_handler(), resolve_to=[PUBLIC_IP])
    with pytest.raises(FetchBlockedError, match="port"):
        await fetcher.fetch("https://example.com:8443/")
    await fetcher.close()
