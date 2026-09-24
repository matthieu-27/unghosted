# ADR 0011 — Mail send and tracker row update are decoupled

- Status: accepted (phase 4)
- Date: 2026-09-24

## Context

Sending a first-contact email (us-5) has two effects that live in different
stores: the SMTP delivery (external side effect, irreversible) and the
tracker row update (`date_sent`, `last_contact`, `cv`, `customised_letter`
cells in MongoDB). A concurrent edit can bump the row's revision between the
read and the write, so the row update can fail *after* the email is out.

## Options

1. **Transactional coupling** — reject the send if the row write fails.
   Impossible: SMTP delivery has no rollback, and no cross-store transaction
   spans an external SMTP provider.
2. **Saga with retries until success** — keep retrying in the background.
   Hides failures from the user and needs a durable outbox, which the MVP
   queue (ADR 0007) doesn't provide yet.
3. **One optimistic retry, then a surfaced failure** — reuse the stale
   revision once, and if the second attempt still conflicts, the email is
   recorded as sent, the row stays untouched, and the API answers `409
   row_update_failed` with instructions to update the row manually.

## Decision

Option 3. The email, thread, and message rows plus the audit event are all
written (the truth of what was sent), the user gets an explicit error telling
them the row needs a manual update, and the UI maps the error code to a
sentence explaining exactly that.

## Consequences

- The sent list and the Mailpit inbox always reflect reality, even when the
  row lags behind.
- The user sees one honest error instead of a silent background divergence.
- The 7-day recipient cooldown is computed from the message rows, not the
  row cells, so a failed row update neither blocks nor permits a duplicate
  send incorrectly.
- When the reply worker (post-MVP) needs guaranteed row updates, this becomes
  the outbox pattern on the job queue.
