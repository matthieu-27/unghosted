# ADR 0001 — Data stores: PostgreSQL + MongoDB + file storage behind an interface

- Status: accepted (phase 1)
- Deciders: owner + assistant
- Date: 2026-09-21

## Context

Unghosted needs strongly structured relational data (projects, contacts, email metadata, audit) and flexible user-shaped data (tracker columns and cells defined per project by templates). The RNCP37873 certification explicitly requires designing a relational database and developing both SQL and NoSQL data-access components, so a polyglot store also serves the academic need. Uploaded and generated files (CVs, letters, housing files) are binary blobs with encryption and retention requirements, not database rows.

## Options

1. **PostgreSQL only** (JSONB for tracker data). One store, ACID everywhere. Rejected: JSONB cell storage would bury the NoSQL data-access competency, and per-project dynamic schemas fit document storage better.
2. **MongoDB only.** Rejected: auth, contacts, threads, audit, and the job queue want relational integrity and constraints.
3. **PostgreSQL (schema `app`) + MongoDB (db `unghosted`) + file storage behind an interface.** Chosen.

## Decision

Split per `docs/diagrams/mld.dbml` and `docs/diagrams/mongo-model.puml`:

- **PostgreSQL** — anything with identity, relations, or audit: projects, contacts, contact↔row links, documents + `document_texts`, applicant_profiles (content as jsonb columns), mailbox connections, email_threads/email_messages + `email_contents`, mail templates/drafts/proposals, link_analyses (cleaned page text and raw model output as jsonb columns), jobs, audit_events. (No `project_versions` or `export_jobs`: projects aren't versioned — dropped by owner decision 2026-09-21. PDF export runs as an `export` job tracked in `jobs`.) Schema `auth` belongs to Better Auth and is never read by the Python API.
- **MongoDB** — **the tracker only** (minimal-Mongo decision, 2026-09-21): `tracker_definitions` and `tracker_rows`. The tracker is the one document-shaped object — its columns are user-defined per project, so its schema lives in application code, not in the database. Definition edits and row edits share one revision domain in one store. Collections carry `$jsonSchema` validators for shape.
- **File storage** — behind a storage gateway interface with two implementations selected by configuration: local filesystem volume (dev, CI, staging) and AWS S3 (production), per `docs/diagrams/storage-layout.puml`.

**No S3-compatible server in dev:** the gateway interface is the seam. A local directory exercises the same application code path minus the HTTP transport. Both implementations pass the same contract test suite (write, read as stream, delete, missing-key, large file). The S3 implementation is tested in CI with moto (in-process mock. Active — releases every 1–2 weeks, docs.getmoto.org), and the real bucket only in the AWS deploy pipeline's smoke test. A dev S3 server (MinIO) would add a container without changing what the tests prove.

**Encryption** is done by the application identically for both backends: envelope encryption per file (random AES-256-GCM data key encrypts content. Master key wraps the data key — config key in dev/staging, AWS KMS in production). Encrypted data key + algorithm version live in `documents`. Same mechanism as OAuth tokens. Files download only through the API (ownership check per request, decrypted stream). No presigned URLs, never rendered inline from the app origin.

**Key rejection rule:** any user-supplied key reaching MongoDB is rejected if it starts with `$` or contains `.` (NoSQL injection).

## Consequences

- Cross-store consistency must be designed explicitly — see ADR 0006 (write order, compensation, reconciliation command).
- Two databases to operate and back up in both environments.
- The certification's relational and NoSQL components are both real, not staged.
- Retention purges run as our own jobs in every environment (not storage lifecycle rules), so behavior is identical everywhere.
