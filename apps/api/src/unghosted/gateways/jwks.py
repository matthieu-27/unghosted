"""Better Auth JWKS retrieval and caching (ADR 0002).

The API never reads Better Auth's tables. It verifies tokens locally
against the public key set served by the web app, keeping the two
services coupled by one HTTP endpoint only.

Key rotation: an unknown ``kid`` triggers one refetch, rate-limited so a
flood of forged ``kid`` values cannot turn this into a request amplifier.
"""

from __future__ import annotations

import time

import httpx
from jwt import PyJWK, PyJWKSet
from jwt.exceptions import PyJWKSetError


class JwksError(Exception):
    """The key set could not be fetched, parsed, or did not hold the key."""


class JwksClient:
    """Fetches and caches the key set for one JWKS URL."""

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float,
        min_refresh_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout_seconds
        self._min_refresh_seconds = min_refresh_seconds
        self._client = client
        self._owns_client = client is None
        self._keys: dict[str, PyJWK] = {}
        self._last_fetch: float | None = None

    async def key_for(self, kid: str) -> PyJWK:
        """Return the verification key for ``kid``, refreshing on a miss."""
        key = self._keys.get(kid)
        if key is not None:
            return key
        if self._may_refresh():
            await self._refresh()
            key = self._keys.get(kid)
            if key is not None:
                return key
        raise JwksError(f"no key {kid!r} in the key set")

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _may_refresh(self) -> bool:
        if self._last_fetch is None:
            return True
        return time.monotonic() - self._last_fetch >= self._min_refresh_seconds

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _refresh(self) -> None:
        client = self._ensure_client()
        self._last_fetch = time.monotonic()
        try:
            response = await client.get(self._url, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JwksError(f"cannot read the key set at {self._url}: {exc}") from exc
        try:
            key_set = PyJWKSet.from_dict(payload)
        except (PyJWKSetError, AttributeError, TypeError) as exc:
            raise JwksError(f"malformed key set at {self._url}: {exc}") from exc
        self._keys = {key.key_id: key for key in key_set.keys if key.key_id}
