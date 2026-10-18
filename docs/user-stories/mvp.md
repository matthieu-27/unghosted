# MVP user stories

[← All user stories](./README.md)

The MVP-only view of `docs/mvp.md`. Each story below is the full file with
post-MVP items removed. Numbering matches the source files (MVP build
order: M1 projects + tracker → M2 paste flow → M3 documents + profile →
M4 letter + first contact + send).

Authentication is post-MVP: the API runs with a seeded owner
(`UNGHOSTED_SEED_USER_ID`). Sending runs through the SMTP gateway against
Mailpit — no OAuth mailboxes in the MVP.

## 1 — Projects

1. **Create project.** As a user I create a project from a template so the
   tracker is preconfigured.
   AC: modal offers `apprenticeship-search` and `rental-search`. Template
   settings validated against the template schema. Project appears in Mongo
   (definition) and Postgres (project row) with documented write order.
2. **Dashboard.** AC: cards show name, template, last activity. Active and
   archived projects separated. Empty state invites first project.
3. **Open workspace.** AC: left rail sections are URL state. Deep link
   restores section, sort, filters. Top chrome ≤ 150 px.
4. **Archive / duplicate / rename / delete.** AC: archive hides from active
   list. Duplicate copies definition + rows. Delete is soft, purged by
   retention job.

## 2 — Tracker editing

1. **Edit cell.** As a user I click or keyboard-navigate to a cell and type
   so data entry is fast.
   AC: editor matches column type (date picker, select, checkbox, rating…).
   Enter commits, Escape cancels. Tab/arrows navigate (WAI-ARIA grid
   pattern). Edits batch and autosave after debounce. Save status shown.
2. **Rows.** AC: insert above/below, delete, duplicate, move. Virtualization
   keeps DOM rows bounded (10 000 rows scroll without lag).
3. **Columns.** AC: add column with picked type. Resize. Reorder. Delete.
   Computed columns read-only.
4. **Revision conflicts.** AC: concurrent edit on stale revision returns 409
   with rebase data. Client rebases or reloads. Worker writes go through the
   same operations path with system author.

Copy/paste and undo/redo are post-MVP (owner decision, 2026-09-22).

## 3 — Link analysis ("+ New application")

1. **One paste.** AC: single input accepts URL or pasted text, auto-detected.
   "Fill manually" opens plain form from column definitions, no model.
2. **Fetch safety.** AC: SSRF suite passes — only http/https default ports.
   DNS resolved and private/loopback/link-local/reserved IPv4+IPv6 blocked
   (incl. `169.254.169.254`). Connect to checked IP. Capped redirects
   re-checked. Size + timeout caps. HTML content types only. No JS.
   Per-user rate limit.
3. **Page kind.** AC: deterministic first (JSON-LD, OpenGraph, URL
   patterns). Model only when inconclusive, with confidence. Kinds from
   shared config.
4. **Extraction.** AC: structured data fills first. Model fills the rest
   with schema generated from tracker columns. Invalid fields dropped not
   fatal. Contact addresses verbatim or dropped. Field-level provenance
   returned (structured / meta / model / detection).
5. **Review form.** AC: page kind shown and editable (re-runs extraction).
   Auto-filled markers. Duplicate URL warning. Kind/project mismatch
   warning with continue/cancel. Nothing saved until confirmed. "Write
   first contact" offered after save.

## 4 — Documents and applicant profile

1. **Upload.** AC: PDF-only, 3 MB per file. Type assigned at upload from
   template list (`cv` and `motivation_letter` for apprenticeship,
   `housing_file` for rental). Content sniffed. Storage key renamed. Never
   rendered inline from app origin.
2. **Eligibility enforced.** AC: ineligible types (`id_document`,
   `tax_notice`, `payslip`, `bank_details`, `guarantor_document`) never
   reach the model gateway — proven by a test asserting the gateway isn't
   called.
3. **Profile draft.** AC: model reads eligible docs + project description
   only. Draft has headline, highlights with stable ids, motivation, style
   notes, availability. User edits and approves. Regenerating never
   overwrites the approved version.
4. **Download.** AC: streamed through API with ownership check. Decrypted
   server-side. No presigned URLs.
5. **Consent.** AC: consent screen for model processing of documents.
   Withdrawal honored. (Mailbox consent is post-MVP with OAuth.)

## 5 — Mailbox and sending

Item 1 (OAuth mailboxes) is post-MVP. The MVP sends through the SMTP
gateway (Mailpit in docker-compose). Items below keep their source numbers.

2. **Customised letter (apprenticeship).** AC: drafted from approved
   profile + row + listing text, derived from the user's generic
   `motivation_letter`. Editor + approve. PDF via Playwright, French
   business-letter layout, one page with overflow warning. Stored as
   versioned `generated_customised_letter` linked to row. Language follows
   listing, user can override. The CV is attached as-is, never customized.
3. **First-contact email.** AC: short (3–5 sentences) when letter attached.
   Grounding — `used_highlights` ids exist in approved profile, no leftover
   placeholders, names match contact/company, language respected, no links
   except user's own. Editor shows relied-on facts and warnings.
4. **Attachments.** AC: template-suggested types pre-selected and visible.
   Sensitive types warned explicitly. Sent documents recorded on message +
   audit.
5. **Send.** AC: one explicit click per email, no bulk, no scheduling.
   Daily cap (default 10) and 7-day rule enforced in domain layer with
   timezone-boundary tests. Human-reply exception applies. Thread headers
   correct for follow-ups.
6. **Recording.** AC: message + thread ids stored. Final sent text +
   attachments stored (not the model proposal). `last_contact`,
   `date_sent`, `cv`, `customised_letter` updated after user sees what will
   change. Audit event.
