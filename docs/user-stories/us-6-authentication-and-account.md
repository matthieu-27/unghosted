# 6 — Authentication and account

[← All user stories](./README.md)

1. **Sign up.** As a visitor I create an account with email + password so my projects are mine.
   AC: valid signup lands on `/projects`. Password requirements enforced by Better Auth. Duplicate email rejected with clear message. Rate-limited.
2. **Log in / log out.** AC: login lands on `/projects`. Unauthenticated access to any app route redirects to `/login`. Logout clears session. Session cookie httpOnly, Secure, SameSite.
3. **API rejects bad tokens.** AC: Python API returns 401 for missing, expired, malicious JWT. Verifies signature against Better Auth JWKS, `iss`/`aud`/`exp`/`nbf`.
4. **Delete account.** AC: every mailbox token revoked at provider. Cascade deletes Postgres, Mongo, file storage data via the documented consistency flow. Audit event written.
