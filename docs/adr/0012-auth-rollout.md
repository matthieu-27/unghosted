# ADR 0012 — Authentication rollout: UUID ids, `auth` schema, seeded owner removed

- Status: accepted (M5)
- Date: 2026-09-24

## Context

ADR 0002 fixed the design: Better Auth owns sessions, its JWT plugin issues short-lived tokens, Litestar verifies them against the JWKS endpoint. M1–M4 shipped before that existed and ran on a seeded owner id (`UNGHOSTED_SEED_USER_ID`) injected by the `current_user` dependency. Turning the design on raised four questions the ADR didn't answer.

## Decisions

### 1. Better Auth generates UUID ids

`advanced.database.generateId: "uuid"`. Every `owner_user_id` in the `app` schema is a `uuid` column. Better Auth's default random string ids would have forced either a column migration across ten tables or a string-typed identity in the domain. The JWT `sub` is parsed as a UUID in `api/auth.py`; anything else is a 401.

### 2. Better Auth's tables live in the `auth` schema

The pg `Pool` opens connections with `search_path=auth`, and the Better Auth CLI creates `user`, `session`, `account`, `verification` and `jwks` there. Alembic never sees them, the Python API never queries them. The schema itself is infrastructure: `infra/postgres-init/01-schemas.sql` creates `app` and `auth` on a fresh volume, existing volumes need the two `CREATE SCHEMA IF NOT EXISTS` statements once.

### 3. The seeded owner is gone, not kept as a fallback

`UNGHOSTED_SEED_USER_ID` is deleted from the settings. A fallback identity would mean a misconfigured deployment serving one shared account instead of failing, with nothing in the response to show it. With the setting gone, a request without a verifiable token can't reach a handler at all.

### 4. Tokens are verified with PyJWT against a cached key set

`gateways/jwks.py` fetches the key set with the project's `httpx`, caches it in process, and refetches once on an unknown `kid` — rate-limited (at most one fetch per 10 s) so forged key ids can't amplify requests towards the web app. PyJWT's own `PyJWKClient` was rejected: it fetches with blocking `urllib` inside an async service.

Tests sign real Ed25519 tokens with a throwaway key served through a stub JWKS transport. The rejection suite covers expiry, `nbf`, tampered payload, foreign key, unknown `kid`, missing `kid`, wrong `iss`, wrong `aud`, `alg=none` and a non-UUID subject.

## Consequences

- Deployments must set `UNGHOSTED_AUTH_ISSUER`, `UNGHOSTED_AUTH_AUDIENCE` and `UNGHOSTED_AUTH_JWKS_URL` to the web app's base URL. The defaults target `http://localhost:3000`, which is a development convenience, not a safe production default.
- `Secure` on the session cookie follows Better Auth's `useSecureCookies`, which keys off an `https` base URL. Local HTTP development gets `HttpOnly` and `SameSite=Lax` only.
- Email verification and password reset stay off in M5. Both need transactional email to a real inbox and are recorded as open work.
- Account deletion (user story 6, item 4) belongs to the GDPR phase, where the cascade across PostgreSQL, MongoDB and file storage is built.
