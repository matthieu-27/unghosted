"""Bearer-token authentication against Better Auth's JWKS (ADR 0002, us-6 item 3).

Every request carries a short-lived JWT issued by the web app's Better Auth
JWT plugin. Verification is local: signature against the cached key set,
then `iss`, `aud`, `exp` and `nbf`. The owner's identity is the `sub`
claim — the API never reads Better Auth's tables.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import jwt
from litestar.exceptions import NotAuthorizedException
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult

from unghosted.gateways.jwks import JwksError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

    from unghosted.config import Settings
    from unghosted.gateways.jwks import JwksClient

_BEARER_PREFIX = "bearer "

REQUIRED_CLAIMS = ["sub", "exp", "iss", "aud"]
"""Claims a token must carry. A token missing one is rejected before any
business code runs, so a handler never sees a partially trusted identity."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """Identity handed to handlers as `request.user`."""

    user_id: uuid.UUID
    email: str | None = None


class JwtAuthMiddleware(AbstractAuthenticationMiddleware):
    """Rejects any request without a verifiable Better Auth JWT."""

    async def authenticate_request(
        self, connection: ASGIConnection[Any, Any, Any, Any]
    ) -> AuthenticationResult:
        token = _bearer_token(connection.headers.get("authorization"))
        settings: Settings = connection.app.state.settings
        jwks: JwksClient = connection.app.state.jwks_client

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise _unauthorized("malformed token") from exc
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise _unauthorized("token without a key id")

        try:
            key = await jwks.key_for(kid)
        except JwksError as exc:
            raise _unauthorized("unknown signing key") from exc

        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=settings.auth_algorithms,
                issuer=settings.auth_issuer,
                audience=settings.auth_audience,
                leeway=settings.auth_leeway_seconds,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as exc:
            raise _unauthorized("invalid token") from exc

        return AuthenticationResult(user=_user_from(payload), auth=payload)


def _bearer_token(header: str | None) -> str:
    if header is None:
        raise _unauthorized("missing bearer token")
    if not header.lower().startswith(_BEARER_PREFIX):
        raise _unauthorized("missing bearer token")
    token = header[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise _unauthorized("missing bearer token")
    return token


def _user_from(payload: dict[str, Any]) -> AuthenticatedUser:
    """Better Auth issues UUID ids (advanced.database.generateId), which the
    `owner_user_id` columns store as UUIDs. Anything else is not our token."""
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _unauthorized("invalid token")
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise _unauthorized("token subject is not a user id") from exc
    email = payload.get("email")
    return AuthenticatedUser(
        user_id=user_id,
        email=email if isinstance(email, str) else None,
    )


def _unauthorized(detail: str) -> NotAuthorizedException:
    return NotAuthorizedException(detail=detail, extra={"code": "unauthenticated"})
