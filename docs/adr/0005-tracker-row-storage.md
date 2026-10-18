# ADR 0005 — Tracker row storage: One Mongo document per row, operations log, fractional ordering

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

A tracker holds hundreds to a few thousand rows per project (single-user scale). Rows have dynamic, template-defined columns. Per-cell sparse styles. A revision for optimistic concurrency. And an order that users change by dragging. Autosave batches edits as typed operations.

## Options

1. **Whole tracker as one Mongo document.** Simplest reads. Rejected: concurrent cell edits rewrite the entire document, revision granularity is the whole sheet, and virtualization windows want row-level reads.
2. **Relational row-per-table with EAV columns.** Rejected: column types are user-defined. EAV queries are painful and this is exactly what documents do well.
3. **One document per row** (`tracker_rows`: `project_id`, `order_key`, `cells`, `styles`, `revision`) plus one `tracker_definitions` document per project. Chosen.

## Decision

- **Order:** fractional indexing (string order keys à la Figma), so a move rewrites only the moved row's key — no bulk renumbering, stable sort, virtualization-friendly.
- **Cells:** `{column_key: typed value}` validated by dynamic marshmallow schemas built from the tracker definition. Keys reject leading `$` and `.`.
- **Styles:** sparse — `{column_key: style}` present only for cells differing from defaults.
- **Operations protocol** (api-contract.md): edits arrive as batches of typed ops with `base_revision`. Applied atomically. Revision increments. Stale batches get `409 stale_revision` with rebase data. Undo/redo is client-side over the same op log.
- **Replies write through the same path** with system author (`response_date`, `reply_type`), so revisions, undo history, and audit stay consistent.
- **Recompute:** computed columns (e.g. `days_since_sent`) are derived, not stored.
- Indexes: `(project_id, order_key)`, `(project_id, revision)`.

## Consequences

- Project fetch = 1 definition read + ordered row scan. Fine at this scale and keeps the window query trivial.
- Per-row revision means two users (or user + worker) editing different rows never conflict. Same-row conflicts are rare and resolved by the 409 rebase.
- Fractional keys grow in length over pathological insert sequences. A compaction job can renumber (stretch).
