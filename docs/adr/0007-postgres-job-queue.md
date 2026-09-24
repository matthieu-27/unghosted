# ADR 0007 — Background jobs: PostgreSQL-backed queue, own implementation

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

Reply sync, document text extraction, model calls, exports, purges, and reconciliation run in the worker, not in request handlers (brief §4.5). Prefer PostgreSQL as the queue to avoid a third datastore. A broker only if justified.

## Options (compared 2026-09-21)

1. **Procrastinate** — mature PostgreSQL-native Python queue, async support, retries, scheduling. Strong choice. Adds a dependency with its own worker model, schema, and API to learn and defend.
2. **PgQueuer** — minimalist PostgreSQL queue (`SKIP LOCKED` + `LISTEN/NOTIFY`), actively developed. Lighter, less mature, fewer features (retries/scheduling left to us anyway).
3. **Redis + ARQ/Celery** — rejected: introduces a third datastore for zero functional gain at single-user scale.
4. **Own minimal queue on the `jobs` table.** Poll with `FOR UPDATE SKIP LOCKED`, `run_after` for delayed retries with backoff, `attempts`/`last_error` columns, `locked_at` for stuck-job reclaim. ~150 lines the owner writes and can defend line-by-line to the jury.

## Decision

**Own minimal implementation** on the `jobs` table (schema in `mld.dbml`), job types: `reply_sync`, `doc_text_extract`, `model_call`, `export`, `purge`, `reconcile`. Jobs are idempotent (all handlers designed for at-least-once execution). Retries use exponential backoff via `run_after`. The worker is the same Python codebase as the API with a separate entrypoint (`python -m unghosted.worker`). Queue health (depth, oldest job, failures) is monitored via the `jobs` table.

Escape hatch: if scheduling needs grow (cron-style recurring jobs with complex timing), move to Procrastinate without changing job payloads.

## Consequences

- Zero new infrastructure. One less service in both deployments.
- The queue is an SQL competency artifact for the certification (competency 8).
- We own retry/backoff/locking correctness — covered by tests (double-enqueue, worker crash mid-job, stuck `locked_at` reclaim).
