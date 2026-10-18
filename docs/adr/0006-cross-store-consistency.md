# ADR 0006 — Cross-store consistency: Write order, compensation, reconciliation

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

Data for one logical action spans PostgreSQL, MongoDB, and file storage (ADR 0001). No distributed transaction spans them. Actions: create/delete project, link contact↔row, store document, record email thread↔row, purge.

## Decision

General rule: **Postgres is the system of record for identity, ownership and relations. Mongo holds the tracker's live content. File storage holds bytes.** Since the minimal-Mongo decision (2026-09-21) the tracker's definition and rows sit in one store, so tracker operations never span stores. Only these flows do. Each defines a write order and a compensation, and an idempotent `reconcile` command finds orphans in every direction, run from a `reconcile` job (scheduled + on demand).

| Flow | Write order | Compensation on failure |
|---|---|---|
| Create project | 1. Postgres `projects` row + seeded mail templates → 2. Mongo `tracker_definitions` (instantiated from the template JSON) | If step 2 fails: project marked `degraded` in Postgres, retry job recreates Mongo docs (definitions are template-derived, idempotent upsert). No orphan: reconcile detects project without definition and reseeds. |
| Delete project | 1. Soft-delete in Postgres → 2. purge job deletes Mongo tracker docs + storage objects → 3. hard-delete Postgres rows last | Purge job is idempotent and retried. Soft-deleted projects are invisible to reads, so partial purge is never user-visible. |
| Contact↔row link | 1. Postgres `contact_row_links` row (authoritative) → 2. cell update via operations (Mongo, bumps revision) | If 2 fails: link exists, cell stale — reconcile rewrites cells from link table. |
| Document upload | 1. storage put (encrypted) → 2. Postgres `documents` row → 3. enqueue text-extraction job | If 2 fails: storage key without row — reconcile deletes orphan objects (keys carry user+id prefixes). |
| Send email | 1. provider send → 2. Postgres thread/message/attachments/email content → 3. operations update row cells in Mongo (`last_contact`, `date_sent`, doc links — after user confirmation) → 4. audit event | If send succeeded but 2/3 fail: provider id exists. Retry job re-fetches provider state and completes records (idempotent by provider_message_id). If send failed: nothing recorded beyond `mail_drafts` state. |
| Reply fields | worker writes tracker ops in Mongo + audit event in Postgres | Operations are atomic. Audit failure retries without user impact. |

**Reconciliation command** (`reconcile` job): for each store direction, list keys absent from the system of record — Mongo tracker docs without a live project, storage objects without a document row, contact link rows whose cell no longer matches, email threads pointing at deleted rows — and repair per the compensation column or delete orphans. Same code in all environments.

## Consequences

- Every flow above gets a failure-injection test in phase 3 (kill step 2, rerun reconcile, assert convergence).
- Reconciliation doubles as the GDPR delete auditor: account deletion converges to zero orphans, asserted by test.
- Purges and reconcile are our jobs, not storage lifecycle rules — identical behavior in dev, staging, production.
