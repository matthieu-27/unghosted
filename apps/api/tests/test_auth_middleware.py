"""JWT verification against the Better Auth key set (us-6 item 3, ADR 0002)."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from litestar import Litestar, get
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide
from litestar.middleware import DefineMiddleware
from litestar.testing import AsyncTestClient

from conftest import (
    AUTH_ISSUER,
    JWKS_URL,
    OWNER_USER,
    TEST_KID,
    issue_token,
    public_jwk,
)
from unghosted.api.auth import JwtAuthMiddleware
from unghosted.api.deps import provide_current_user
from unghosted.config import Settings, load_settings
from unghosted.gateways.jwks import JwksClient, JwksError


@get("/whoami")
async def whoami(current_user: NamedDependency[uuid.UUID]) -> dict[str, str]:
    return {"user_id": str(current_user)}


@get("/open", exclude_from_auth=True)
async def open_route() -> dict[str, str]:
    return {"status": "ok"}


def build_app(jwks: JwksClient, settings: Settings) -> Litestar:
    """A minimal app carrying the real middleware and the real dependency."""
    return Litestar(
        route_handlers=[whoami, open_route],
        middleware=[DefineMiddleware(JwtAuthMiddleware)],
        dependencies={
            "current_user": Provide(provide_current_user, sync_to_thread=False)
        },
        state=State({"settings": settings, "jwks_client": jwks}),
    )


def jwks_client(http: httpx.AsyncClient) -> JwksClient:
    return JwksClient(url=JWKS_URL, timeout_seconds=1.0, client=http)


def mock_http(document: dict[str, Any]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=document)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def call_whoami(
    jwks_document: dict[str, Any],
    settings: Settings,
    headers: dict[str, str],
) -> httpx.Response:
    async with mock_http(jwks_document) as http:
        app = build_app(jwks_client(http), settings)
        async with AsyncTestClient(app=app) as client:
            return await client.get("/whoami", headers=headers)


@pytest.fixture
def settings() -> Settings:
    return load_settings()


async def test_valid_token_identifies_the_owner(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key)
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == str(OWNER_USER)


async def test_missing_header_is_rejected(
    jwks_document: dict[str, Any], settings: Settings
) -> None:
    response = await call_whoami(jwks_document, settings, {})
    assert response.status_code == 401
    assert response.json()["extra"]["code"] == "unauthenticated"


@pytest.mark.parametrize(
    "header",
    ["Token abc", "Bearer", "Bearer    ", "abc"],
)
async def test_malformed_authorization_header_is_rejected(
    jwks_document: dict[str, Any], settings: Settings, header: str
) -> None:
    response = await call_whoami(jwks_document, settings, {"Authorization": header})
    assert response.status_code == 401


async def test_expired_token_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, lifetime_seconds=60, issued_at_offset=-3600)
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_not_yet_valid_token_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, issued_at_offset=3600)
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_tampered_payload_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key)
    header_b64, payload_b64, signature_b64 = token.split(".")
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    payload["sub"] = str(uuid.uuid4())
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    )
    forged = f"{header_b64}.{forged_payload}.{signature_b64}"

    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {forged}"}
    )
    assert response.status_code == 401


async def test_token_from_another_key_is_rejected(
    jwks_document: dict[str, Any], settings: Settings
) -> None:
    # Same kid, different private key: the signature must not verify.
    attacker_key = Ed25519PrivateKey.generate()
    token = issue_token(attacker_key)
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_unknown_kid_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, kid="rotated-away")
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_token_without_kid_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, kid=None)
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_wrong_issuer_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, issuer="https://evil.example")
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_wrong_audience_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, audience="https://other.example")
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_unsigned_token_is_rejected(
    jwks_document: dict[str, Any], settings: Settings
) -> None:
    # alg=none, the classic downgrade: the key set only serves EdDSA keys.
    token = jwt.encode(
        {"sub": str(OWNER_USER), "iss": AUTH_ISSUER, "aud": AUTH_ISSUER},
        key="",
        algorithm="none",
        headers={"kid": TEST_KID},
    )
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_non_uuid_subject_is_rejected(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any], settings: Settings
) -> None:
    token = issue_token(signing_key, subject="not-a-uuid")
    response = await call_whoami(
        jwks_document, settings, {"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_route_marked_public_needs_no_token(
    jwks_document: dict[str, Any], settings: Settings
) -> None:
    async with mock_http(jwks_document) as http:
        app = build_app(jwks_client(http), settings)
        async with AsyncTestClient(app=app) as client:
            response = await client.get("/open")
    assert response.status_code == 200


async def test_key_set_refresh_serves_a_rotated_key(
    signing_key: Ed25519PrivateKey, jwks_document: dict[str, Any]
) -> None:
    """A key added after the first fetch is picked up on the next miss."""
    rotated_key = Ed25519PrivateKey.generate()
    served: list[dict[str, Any]] = [jwks_document]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=served[0])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = JwksClient(
            url=JWKS_URL, timeout_seconds=1.0, min_refresh_seconds=0.0, client=http
        )
        assert (await client.key_for(TEST_KID)).key_id == TEST_KID
        served[0] = {
            "keys": [
                public_jwk(signing_key),
                public_jwk(rotated_key, kid="rotated"),
            ]
        }
        assert (await client.key_for("rotated")).key_id == "rotated"


async def test_unknown_kid_refresh_is_rate_limited(
    jwks_document: dict[str, Any],
) -> None:
    """Forged key ids must not turn the API into a JWKS request amplifier."""
    fetches = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetches
        fetches += 1
        return httpx.Response(200, json=jwks_document)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = JwksClient(
            url=JWKS_URL, timeout_seconds=1.0, min_refresh_seconds=600.0, client=http
        )
        for _ in range(5):
            with pytest.raises(JwksError):
                await client.key_for("forged")
    assert fetches == 1


async def test_unreachable_key_set_raises(jwks_document: dict[str, Any]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = JwksClient(url=JWKS_URL, timeout_seconds=1.0, client=http)
        with pytest.raises(JwksError):
            await client.key_for(TEST_KID)
