# ADR 0002 — Authentication: Better Auth sessions + JWT/JWKS for the Python API

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

The web app (TanStack Start, Bun) owns the browser session. The Python API (Litestar) serves all business data and must authenticate requests without sharing Better Auth's database schema. Mailbox OAuth (Gmail/Microsoft) is a data connection, not a sign-in method.

## Options

1. **Shared session cookie read by the Python API.** Rejected: the API would need to read Better Auth's `auth` schema, coupling two services to third-party tables.
2. **Better Auth JWT plugin + local JWKS verification in Litestar.** Chosen.
3. **Opaque tokens issued by a dedicated service.** Rejected: invents a token service and a key store for no gain.

## Decision

- Better Auth runs inside TanStack Start (server routes), users/sessions/accounts in PostgreSQL schema `auth`, managed by Better Auth's own migrations. Browser sessions = httpOnly, Secure, SameSite cookies.
- Better Auth's **JWT plugin** issues short-lived JWTs for the API. Its JWKS endpoint serves public keys at `GET /api/auth/jwks` (RFC 7517. Docs: better-auth.com/plugins/jwt). Litestar verifies **locally**: fetch the key set once, cache it, refresh on unknown `kid`. Checks `iss`, `aud`, `exp`, `nbf`. User id comes from `sub`. Default issuer/audience = the web app's base URL. Algorithm from the plugin's key config (EdDSA/ES256/ES512/PS256/RS256).
- The web API client obtains and refreshes tokens in one module. Tokens never touch `localStorage`.
- Password hashing: Better Auth default (scrypt) — no documented reason to change.
- Rate limiting on auth endpoints. CSRF protection on cookie routes.

## Consequences

- The Python API depends only on the JWKS endpoint over HTTP, not on auth tables — services stay decoupled.
- Key rotation is handled by refreshing on unknown `kid`. Revoked sessions die with token expiry (short-lived).
- Phase 2 test plan must cover expired and tampered tokens, and wrong `iss`/`aud`.
