# API contract draft — `/api/v1`

Served by Litestar. OpenAPI specification generated from code. Route list lives in `docs/naming-table.md`. This draft defines envelopes, the operations protocol, and error model. Final JSON Schemas will live in `packages/shared/schemas/` and be consumed by both the API (marshmallow, generated from the same definitions) and the web forms.

## Authentication

- Browser authenticates against Better Auth on the TanStack Start server (cookie session).
- The web API client obtains a short-lived JWT from Better Auth's token endpoint and sends `Authorization: Bearer <jwt>` to the Python API. Token never touches `localStorage`. Refresh handled in the API client module only.
- Litestar verifies locally against `GET /api/auth/jwks` (RFC 7517) with key cache + refresh on unknown `kid`. Validates `iss`, `aud`, `exp`, `nbf`. User id = `sub`.

## Envelopes

Success: the resource or `{ "data": .. }` for lists with pagination metadata:

```json
{ "data": [..], "page": {"number": 1, "size": 50, "total": 120} }
```

Error:

```json
{ "error": { "code": "stale_revision", "message": "Tracker moved on", "details": { "current_revision": 42 } } }
```

Unknown fields in request bodies are rejected (marshmallow `RAISE`). Keys reaching MongoDB are checked: no leading `$`, no `.`.

## Tracker operations protocol

`PATCH /projects/{projectId}/tracker/operations`

```json
{
  "base_revision": 41,
  "operations": [
    { "op": "set_cell", "row_id": "…", "column_key": "company", "value": "Acme" },
    { "op": "set_cell_style", "row_id": "…", "column_key": "status", "style": { "bold": true } },
    { "op": "insert_rows", "after_row_id": "…", "count": 1 },
    { "op": "delete_rows", "row_ids": ["…"] },
    { "op": "move_row", "row_id": "…", "after_row_id": "…" },
    { "op": "insert_column", "after_column_key": "notes", "column": { "key": "priority", "type": "select", "options": [..] } },
    { "op": "update_column", "column_key": "priority", "column": { "options": [..] } },
    { "op": "delete_column", "column_key": "priority" },
    { "op": "move_column", "column_key": "priority", "after_column_key": "status" },
    { "op": "resize_column", "column_key": "company", "width": 180 },
    { "op": "clear_formatting", "cells": [{"row_id": "…", "column_key": "status"}] }
  ]
}
```

Rules:

- Applied atomically per batch. Server increments revision. Response returns new revision + echoes applied ops.
- `base_revision` mismatch → `409 stale_revision` with `current_revision` and enough state for the client to rebase.
- Reply worker uses the same endpoint with system author. Its ops (`set_cell` on `response_date`/`reply_type`, `set_cell` on `last_contact` via proposal acceptance) are marked `author: "system"` in the audit log.
- `set_cell` values validated against dynamic schemas built from column definitions. Select values must exist. Contact/document links must resolve to ids owned by the project.
- System columns (`response_date`, `reply_type`) reject `set_cell` from user author — they're worker-only plus manual-correction flag.

## Cell value shapes by column type

| Type | JSON shape |
|---|---|
| text, long-text, url, email, phone | string |
| number, currency, percent, rating | number |
| date | ISO `YYYY-MM-DD` |
| select | option key (string) |
| checkbox | boolean |
| contact-link | array of contact ids |
| document-link | array of document ids |
| computed | read-only. Server/client computes |

Sparse styles: `{ bold?, italic?, underline?, strike?, color?, fill?, align?, wrap?, number_format? }` — omitted keys inherit defaults.

## Error codes

| Code | HTTP | Used for |
|---|---|---|
| `unauthenticated` | 401 | missing/expired/invalid JWT |
| `forbidden` | 403 | resource not owned by caller |
| `not_found` | 404 | |
| `validation_failed` | 422 | field errors in `details` |
| `stale_revision` | 409 | tracker concurrency |
| `sending_cap_exceeded` | 429 | daily cap or 7-day rule.`details.retry_at` / `details.next_allowed_date` |
| `mailbox_disconnected` | 409 | send/sync on revoked connection |
| `attachment_too_large` | 422 | provider limit.`details.limit_bytes` |
| `rate_limited` | 429 | generic rate limit (auth, link analysis) |
| `fetch_blocked` | 422 | SSRF policy or fetch failure in link analysis |

## Rate limits

Auth endpoints, link analysis (per user), and downloads are rate-limited. Limits in response headers.

## Notes

- All list endpoints paginated. Tracker fetch returns definition + rows + revision in one payload.
- Project resources embed the template's `document_types` (`key`, `label`, `model_eligible`): the upload form offers exactly these, and `model_eligible` drives the consent gate and eligibility rules (ADR 0009). Full shapes come from the OpenAPI specification generated from code.
- Exports: xlsx/csv/json stream synchronously. PDF renders via a worker job (`jobs` type `export`) and downloads when done — no dedicated table, the job row tracks status.
- Webhooks/callbacks: none in v1. Mailbox sync is scheduled polling (ADR 0010 notes push option).
