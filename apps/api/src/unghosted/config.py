"""Application settings, loaded from the environment (12-factor)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Everything the API and worker read from configuration.

    Secrets never have defaults: a missing value must fail startup, not
    silently connect somewhere unexpected.
    """

    model_config = SettingsConfigDict(
        env_prefix="UNGHOSTED_", env_file=".env", extra="ignore"
    )

    database_url: str
    """PostgreSQL DSN for the app schema, e.g. postgresql+asyncpg://user:pass@host:5433/unghosted"""

    mongo_url: str
    """MongoDB URL, e.g. mongodb://user:pass@localhost:27018"""

    mongo_database: str = "unghosted"

    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    """Better Auth JWKS endpoint. Keys are fetched once and cached, then
    refetched when a token carries an unknown `kid` (ADR 0002)."""

    auth_issuer: str = "http://localhost:3000"
    """Expected `iss`. Better Auth defaults it to the web app's base URL."""

    auth_audience: str = "http://localhost:3000"
    """Expected `aud`. Better Auth defaults it to the web app's base URL."""

    auth_algorithms: list[str] = ["EdDSA"]
    """Accepted signature algorithms. Better Auth's JWT plugin signs with
    Ed25519 by default; an empty or wider list would accept weaker keys."""

    auth_leeway_seconds: float = 5.0
    """Clock-skew allowance on `exp` and `nbf`."""

    auth_jwks_timeout_seconds: float = 5.0
    """Time cap for one JWKS fetch."""

    shared_templates_dir: Path = (
        Path(__file__).resolve().parents[4] / "packages" / "shared" / "templates"
    )
    """Where template JSONs live. Default: the monorepo
    packages/shared/templates relative to this file (src layout runs
    editable). Override when the package is installed elsewhere."""

    cors_origins: list[str] = []
    """Allowed browser origins for the API."""

    mistral_api_key: str | None = None
    """Mistral API key (ADR 0008). None disables the model gateway: link
    analysis falls back to deterministic fields plus manual entry."""

    mistral_model: str = "mistral-small-latest"
    """Pinned Mistral model for extraction and classification tasks."""

    fetch_max_bytes: int = 2_097_152
    """Size cap for link-analysis page fetches (SSRF suite, us-3 item 2)."""

    fetch_timeout_seconds: float = 15.0
    """Total time cap for one link-analysis fetch including redirects."""

    storage_backend: Literal["local", "s3"] = "local"
    """Which storage gateway implementation serves files (ADR 0001). S3 is
    exercised in CI with moto; production selects it at deploy time."""

    storage_dir: Path = Path("var/storage")
    """Local filesystem root for the local storage backend. Windows dev and
    compose override this; never committed to git."""

    master_key: str
    """Base64 32-byte key wrapping each file's AES-256-GCM data key
    (envelope encryption, ADR 0001). Dev/staging come from config, AWS KMS
    replaces this post-MVP."""

    s3_bucket: str | None = None
    """Bucket name when storage_backend is s3."""

    s3_endpoint_url: str | None = None
    """Custom S3 endpoint. Tests point this at an in-process moto server."""

    s3_region: str | None = None
    """AWS region when storage_backend is s3 (default credential chain)."""

    smtp_host: str = "localhost"
    """SMTP relay for outbound mail. M4 targets Mailpit (compose service);
    Gmail and Graph replace the gateway post-MVP, not this setting."""

    smtp_port: int = 1025
    """Mailpit's SMTP port. Port 25/587 providers need an explicit override."""

    smtp_timeout_seconds: float = 10.0

    mail_from: str = "applicant@example.com"
    """From address while no mailbox is connected (MVP). The sender identity
    moves to the user's own mailbox post-MVP; this default is demo-only."""

    daily_send_cap: int = 10
    """Per project, per project-local day (us-5 item 5)."""

    send_timezone: str = "Europe/Paris"
    """The zone the daily cap and the date_sent cell live in (us-5 item 5)."""


def load_settings() -> Settings:
    """Parse settings once at startup; pydantic raises on missing values."""
    return Settings()
