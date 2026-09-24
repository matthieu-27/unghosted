# Naming table — approved identifiers

Approved 2026-09-21 (phase 1). Every new name in code, schemas, and docs comes from this table or a later approved amendment. Trivial local variables are exempt.

## Conventions

- PostgreSQL tables/columns, Mongo fields, JSON keys: `snake_case`.
- API path segments, file routes, template keys: `kebab-case`.
- Python modules/packages: `snake_case`. Classes `PascalCase`. Functions `snake_case`.
- UI strings live in template JSONs and the web i18n catalog, never inline.

## Top identifier

| Name | Kind | Purpose |
|---|---|---|
| `unghosted` | repo, root package, Python package, Docker images, database names | Technical identifier everywhere |

## Templates (`packages/shared/templates/`)

| Key | Purpose |
|---|---|
| `apprenticeship-search` | Work-study/apprenticeship search (base: Le Dojo Club model) |
| `rental-search` | Rental search |

<!-- vale write-good.TooWordy = NO -->
<!-- Suppressed on this line only: "purchase" is part of the template name, not prose. -->
Blank template dropped. Property-purchase deferred to stretch goals.
<!-- vale write-good.TooWordy = YES -->

## PostgreSQL — schema `app`

All tables: `id uuid primary key`, `created_at`, `updated_at`. Schema `auth` belongs to Better Auth. The Python API never reads it.

| Table | Purpose |
|---|---|
| `projects` | owner user id, name, description, template key + version, archived flag, soft-delete marker |
| `contacts` | per-project contact: name, role, organization, email, phone, profile url, notes |
| `contact_row_links` | many-to-many: contact ↔ tracker row (row id is the Mongo document id) |
| `documents` | project, type key, model-eligible flag, storage key, encrypted data key + algorithm version, size, checksum, retention date |
| `applicant_profiles` | per project: version number, approved marker, status, content columns (headline, seeking, highlights jsonb, motivation, style notes jsonb, availability) |
| `mailbox_connections` | per user + mailbox: provider, account email, granted scopes, encrypted tokens, sync cursor, status |
| `email_threads` | connection, provider thread id, project, row link, contact link |
| `email_messages` | thread, provider message id, direction, timestamps, reply type, classification |
| `email_message_attachments` | message ↔ document join |
| `mail_templates` | per project: kind, name, subject, body with placeholders |
| `mail_drafts` | draft email linked to row/contact/thread, state |
| `mail_proposals` | status-change / follow-up / template proposal + state |
| `link_analyses` | "+ New application" run: source (url or text), page kind, status, provider, timings, errors, cleaned page text, raw model output (jsonb) |
| `jobs` | job queue: type, payload, status, attempts, run-after, last error |
| `document_texts` | extracted text of eligible documents (FK to documents) |
| `email_contents` | sent email bodies + reply excerpts used for classification (FK to email_messages) |
| `audit_events` | actor, action, target, metadata. Every email sent, mailbox connect/disconnect, manual reply field correction |

## MongoDB — database `unghosted`

| Collection | Purpose |
|---|---|
| `tracker_definitions` | per project: columns, conditional-formatting rules, settings values |
| `tracker_rows` | per row: project id, order key, cells, sparse styles, revision |

## API routes — `/api/v1`

| Route | Purpose |
|---|---|
| `GET /projects`, `POST /projects` | list own, create |
| `GET /projects/{projectId}`, `PATCH /projects/{projectId}`, `DELETE /projects/{projectId}` | read, update (name, description, settings, archive), soft delete |
| `GET /projects/{projectId}/tracker` | definition + rows + revision |
| `PATCH /projects/{projectId}/tracker/operations` | batch of typed operations + last known revision. 409 on stale |
| `GET /projects/{projectId}/contacts`, `POST …/contacts` | list, create |
| `PATCH /projects/{projectId}/contacts/{contactId}`, `DELETE …/contacts/{contactId}` | update, delete |
| `POST /projects/{projectId}/link-analyses` | analyze pasted url/text, returns pre-filled form |
| `POST /projects/{projectId}/documents` | upload (multipart) |
| `GET /projects/{projectId}/documents`, `DELETE …/documents/{documentId}` | list, delete |
| `GET /projects/{projectId}/documents/{documentId}/download` | streamed, ownership-checked, decrypted |
| `POST /projects/{projectId}/profile/drafts` | ask model for profile draft |
| `PATCH …/profile/versions/{version}` | edit draft |
| `POST …/profile/versions/{version}/approve` | approve |
| `GET /projects/{projectId}/mail/templates`, `POST …/mail/templates` | list, create |
| `PATCH …/mail/templates/{templateId}`, `DELETE …/mail/templates/{templateId}` | update, delete |
| `POST /projects/{projectId}/mail/first-contact` | draft first-contact email for a row |
| `POST /projects/{projectId}/mail/follow-ups` | draft follow-up for a row |
| `PATCH /mail/drafts/{draftId}` | edit draft, select attachments, mailbox |
| `POST /mail/drafts/{draftId}/send` | the only send endpoint. Enforces caps |
| `GET /mailbox-connections` | list own connections + sync status |
| `POST /mailbox-connections/{provider}` | start OAuth (provider: `gmail` or `outlook`) |
| `DELETE /mailbox-connections/{connectionId}` | revoke + disconnect |
| `GET /projects/{projectId}/exports/{format}` | synchronous download: xlsx / csv / json |
| `POST /projects/{projectId}/exports/pdf` | queued via `jobs`. Download when done |
| `GET /projects/{projectId}/proposals` | pending proposals (mail inbox) |
| `PATCH /proposals/{proposalId}` | accept / edit / dismiss |
| `GET /account/data-export` | GDPR download |
| `DELETE /account` | GDPR account deletion cascade |

## React routes (`apps/web/src/routes/`)

| Route file | URL | Purpose |
|---|---|---|
| `index.tsx` | `/` | landing (SSR) |
| `login.tsx`, `signup.tsx` | `/login`, `/signup` | auth. `login` carries a `redirect` search param, restricted to own paths |
| `_authed.tsx` | — | pathless guard layout: no session, no entry. Wraps every `_authed.projects.*` route without changing its URL |
| `_authed.projects.index.tsx` | `/projects` | dashboard |
| `_authed.projects.$projectId.overview.tsx` | `/projects/$projectId/overview` | project overview |
| `_authed.projects.$projectId.tracker.tsx` | `/projects/$projectId/tracker` | grid. Sort/filter/selection in search params |
| `_authed.projects.$projectId.contacts.tsx` | `/projects/$projectId/contacts` | contacts |
| `_authed.projects.$projectId.documents.tsx` | `/projects/$projectId/documents` | documents + profile |
| `_authed.projects.$projectId.mail.tsx` | `/projects/$projectId/mail` | mail inbox |
| `account.mailboxes.tsx` | `/account/mailboxes` | connected mailboxes — the "emails" category of the future settings area (categories planned: general, projects, informations, emails. Named when built) |

## Python layout (`apps/api/src/unghosted/`)

| Module | Purpose |
|---|---|
| `domain/` | pure: `stats`, `conditional_rules`, `source_detection`, `eligibility`, `reply_rules`, `placeholders`, `operations`, `sending_limits`, `link_analysis` |
| `services/` | application services orchestrating domain + repositories + gateways |
| `repositories/` | SQL and NoSQL implementations behind interfaces |
| `gateways/` | `model` (provider interface), `gmail`, `graph`, `storage` (local + S3), `jwks` (Better Auth key set) |
| `api/` | Litestar controllers, plus `auth` (JWT middleware, `AuthenticatedUser`) and `deps` (`current_user`) |
| `worker/` | worker entrypoint + job handlers |

## Shared package (`packages/shared/`)

| Path | Purpose |
|---|---|
| `templates/apprenticeship-search.json`, `templates/rental-search.json` | template definitions |
| `source-domains.json` | domain → source mapping, both templates |
| `schemas/*.json` | JSON Schemas for API contracts shared by web + API |

## Select-option keys

Apprenticeship statuses: `to_apply`, `sent`, `followed_up`, `hr_interview`, `technical_interview`, `case_study` (label "Étude de cas"), `final_interview`, `offer`, `accepted`, `rejected`, `declined`, `no_response`, `position_closed`.

Rental statuses: `spotted`, `awaiting_reply`, `visit_scheduled`, `visited`, `accepted`, `rejected`, `listing_removed`, `dropped`.

Reply types: `auto`, `human`. Work modes: `on_site`, `hybrid`, `remote`. Contract types: `permanent`, `fixed_term`, `work_study`, `internship`, `freelance`, `temp`, `vie`.

Document types: `cv`, `motivation_letter` (generic uploads), `generated_customised_letter` (per-application output), `housing_file`, `employment_contract`, `payslip`, `tax_notice`, `id_document`, `guarantor_document`, `bank_details`, `other` — eligibility flags in ADR 0009. Uploads are PDF-only, 3 MB per file.

Tracker column keys: snake_case of the brief's labels. Full lists in `docs/tracker-templates.md`.

## Names rejected

- `extraction_requests`, `extraction_artifacts` — "extraction" jargon. Replaced by `link_analyses` family.
- `project_contacts_links` — names the contact-belongs-to-project relation, which is the `contacts.project_id` FK. The join table is row ↔ contact.
<!-- vale write-good.TooWordy = NO -->
<!-- Suppressed on this line only: "purchase" is part of the template name, not prose. -->
- Blank template, `property-purchase` template — dropped from scope (property-purchase = stretch).
<!-- vale write-good.TooWordy = YES -->
