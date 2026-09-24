# ADR 0010 — Mailbox OAuth scopes (Gmail, Microsoft Graph) and sync mechanics

- Status: accepted (phase 1)
- Date: 2026-09-21
- Scope facts verified against provider docs: 2026-09-21

## Context

The mail assistant sends through the user's own mailbox and detects replies. OAuth 2.0 authorization-code flow with PKCE, handled by the Python API (ADR 0002 keeps it separate from login). Minimal scopes. Testing mode acceptable for Gmail until verification.

## Gmail (chosen scopes)

| Scope | Class | Why |
|---|---|---|
| `https://www.googleapis.com/auth/gmail.send` | sensitive | send messages (the narrowest send scope) |
| `https://www.googleapis.com/auth/gmail.readonly` | restricted | read threads the app sent + replies. History API for incremental sync |

`access_type=offline` for refresh tokens. Not requested: `gmail.compose`/`gmail.modify` (broader, restricted), `mail.google.com/` (full access), `gmail.labels` (unused).

Docs: developers.google.com/gmail/api/auth/scopes — scope classes per that page. Restricted scopes trigger Google's verification and a security assessment for public production use. **We run in testing mode (manually added test users) — acceptable for this project** (brief §7.1). Production approval would require: OAuth verification submission, a CASA security assessment (tier 2 typical for restricted scopes at this volume), privacy policy with the Limited Use disclosure (already planned), and possibly a YouTube demo video. The privacy policy carries the Google-required disclosure statement either way.

## Microsoft Graph (chosen delegated permissions)

| Permission | Why |
|---|---|
| `Mail.Send` | send messages |
| `Mail.ReadWrite` | create draft + **attachment upload sessions** (files 3–150 MB. Direct POST only under 3 MB. Message limit ~35 MB default) — sending real attachments needs it (learn.microsoft.com/en-us/graph/api/attachment-createuploadsession) |
| `offline_access` | refresh tokens |

Delta queries (`/delta`) under `Mail.Read` semantics — covered by `Mail.ReadWrite`. Publisher verification recommended (brief §7.1). App registration in Entra ID.

Notes checked: upload-session flow requires draft creation before send.`Mail.Send` alone can't attach via upload sessions (community-confirmed + docs). If we later cap attachments under 3 MB, `Mail.ReadWrite` could be revisited — the API surface stays behind the gateway either way.

## Token handling

Tokens stored envelope-encrypted (same mechanism as documents, ADR 0001) in `mailbox_connections`. Never logged, never sent to the browser. Refresh failure marks the connection `needs_reconnect` and notifies the user. Disconnect revokes at the provider, deletes tokens, stops sync.

## Sync

Scheduled incremental polling per connection: Gmail **history API** (historyId cursor), Graph **delta queries** (deltaLink cursor). Push notifications (Gmail Pub/Sub, Graph change notifications) require a public HTTPS endpoint — deferred. Revisit note recorded. Data minimization per brief §7.3: only threads the app sent, plus a narrow contact-address fallback. Tested by a fake provider that fails on any out-of-scope read.

## Consequences

- Users see the smallest workable permission screen for each provider.
- Gmail testing mode caps external users until verification is done — fine for a certification project. Documented for the jury.
- Attachment size UX must encode provider limits: pre-send checks show clear errors (Graph ~35 MB message default. Per-file upload session 150 MB. Gmail ~25 MB total).
