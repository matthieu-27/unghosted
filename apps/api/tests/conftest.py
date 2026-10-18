"""Shared fixtures. Integration tests need the compose databases running."""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt.algorithms import OKPAlgorithm

from unghosted.gateways.jwks import JwksClient

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import AsyncTestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
OWNER_USER = uuid.UUID("00000000-0000-4000-8000-000000000001")

# Tokens are signed here with a throwaway Ed25519 key served through a stub
# JWKS endpoint: the verification path under test is the production one
# (ADR 0002), only the issuer is local.
TEST_KID = "unghosted-test-key"
AUTH_ISSUER = "http://localhost:3000"
JWKS_URL = "https://auth.test/api/auth/jwks"


def _read_root_env() -> dict[str, str]:
    """The root .env carries the machine's compose port mapping (a native
    Postgres may own 5432). Tests must follow the same mapping."""
    values: dict[str, str] = {}
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def _configure_env() -> None:
    """Defaults mirror apps/api/.env.example and the compose defaults so a
    local `uv run pytest` works after `docker compose up -d` without any
    .env file. Real UNGHOSTED_* environment variables win."""
    root_env = _read_root_env()
    pg_port = root_env.get("POSTGRES_PORT", "5432")
    mongo_port = root_env.get("MONGO_PORT", "27017")
    os.environ.setdefault(
        "UNGHOSTED_DATABASE_URL",
        f"postgresql+asyncpg://unghosted:unghosted@localhost:{pg_port}/unghosted",
    )
    os.environ.setdefault(
        "UNGHOSTED_MONGO_URL",
        f"mongodb://unghosted:unghosted@localhost:{mongo_port}",
    )
    os.environ.setdefault("UNGHOSTED_AUTH_JWKS_URL", JWKS_URL)
    os.environ.setdefault("UNGHOSTED_AUTH_ISSUER", AUTH_ISSUER)
    os.environ.setdefault("UNGHOSTED_AUTH_AUDIENCE", AUTH_ISSUER)
    os.environ.setdefault(
        "UNGHOSTED_MASTER_KEY",
        # Test-only key: 32 ASCII "0" bytes, base64. Dev machines use a real
        # key in apps/api/.env; this default only ever runs under pytest.
        base64.b64encode(b"0" * 32).decode("ascii"),
    )
    os.environ.setdefault(
        "UNGHOSTED_SHARED_TEMPLATES_DIR",
        str(REPO_ROOT / "packages" / "shared" / "templates"),
    )


_configure_env()


def public_jwk(key: Ed25519PrivateKey, kid: str = TEST_KID) -> dict[str, Any]:
    """The public half of `key` in the shape Better Auth's /jwks returns."""
    document: dict[str, Any] = json.loads(OKPAlgorithm.to_jwk(key.public_key()))
    document["kid"] = kid
    document["alg"] = "EdDSA"
    document["use"] = "sig"
    return document


def issue_token(
    key: Ed25519PrivateKey,
    *,
    subject: uuid.UUID | str = OWNER_USER,
    kid: str | None = TEST_KID,
    issuer: str = AUTH_ISSUER,
    audience: str = AUTH_ISSUER,
    lifetime_seconds: int = 900,
    issued_at_offset: int = 0,
    claims: dict[str, Any] | None = None,
) -> str:
    """Sign a token the way Better Auth's JWT plugin does. Every keyword is
    a knob the rejection tests turn one at a time."""
    now = int(time.time()) + issued_at_offset
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "nbf": now,
        "exp": now + lifetime_seconds,
    }
    payload.update(claims or {})
    headers = {"kid": kid} if kid is not None else None
    return jwt.encode(payload, key, algorithm="EdDSA", headers=headers)


@pytest.fixture(scope="session")
def signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture(scope="session")
def jwks_document(signing_key: Ed25519PrivateKey) -> dict[str, Any]:
    return {"keys": [public_jwk(signing_key)]}


@pytest.fixture
async def stub_jwks(jwks_document: dict[str, Any]) -> AsyncIterator[JwksClient]:
    """A JwksClient reading the stub key set instead of a running web app."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=jwks_document)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        yield JwksClient(url=JWKS_URL, timeout_seconds=1.0, client=http)


@pytest.fixture
def owner_token(signing_key: Ed25519PrivateKey) -> str:
    return issue_token(signing_key)


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Run Alembic to head once per session; per-test cleanup truncates."""
    api_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(api_dir / "alembic.ini")
    alembic_cfg.set_main_option("script_location", str(api_dir / "migrations"))
    command.upgrade(alembic_cfg, "head")


@pytest.fixture
async def client(
    migrated_db: None, stub_jwks: JwksClient, owner_token: str
) -> AsyncIterator[AsyncTestClient[Litestar]]:
    from litestar.testing import AsyncTestClient
    from pymongo import AsyncMongoClient
    from sqlalchemy import text

    from unghosted.app import create_app
    from unghosted.config import load_settings
    from unghosted.db.sql import create_engine

    settings = load_settings()

    # Per-test isolation: wipe both stores before handing the client out.

    mongo: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
        settings.mongo_url,
        uuidRepresentation="standard",
    )
    db = mongo.get_database(settings.mongo_database)
    await db.drop_collection("tracker_definitions")
    await db.drop_collection("tracker_rows")
    await mongo.close()

    engine = create_engine(settings)
    async with engine.begin() as conn:
        # CASCADE reaches documents, document_texts and applicant_profiles
        # through their project FK; consents has no FK, so truncate it too.
        await conn.execute(text("TRUNCATE TABLE app.projects CASCADE"))
        await conn.execute(text("TRUNCATE TABLE app.consents"))
    await engine.dispose()

    app = create_app(settings)
    # The app would otherwise call the real web app for its key set.
    app.state.jwks_client = stub_jwks

    async with AsyncTestClient(app=app) as test_client:
        # Every request in the suite runs as the owner unless a test
        # overrides the header.
        test_client.headers["Authorization"] = f"Bearer {owner_token}"
        yield test_client


@pytest.fixture
def owner_user() -> uuid.UUID:
    return OWNER_USER


async def create_project(
    client: AsyncTestClient[Litestar], template: str, name: str
) -> dict[str, Any]:
    """POST a project for the seeded owner; asserts 201."""
    response = await client.post(
        "/api/v1/projects",
        json={"template_key": template, "name": name, "settings": {}},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())
