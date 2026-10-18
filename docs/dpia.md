# DPIA — AIPD (draft, phase 1. Finalized in phase 10)

Unghosted — project-based application tracker. Data controller: the owner (Matthieu, personal project). French/English mixed audience. Final version will be French where the CNIL format requires.

## 1. Processing description

| Item | Content |
|---|---|
| Purpose | Track job/housing applications. Draft and send application emails through the user's own mailbox. Detect replies. |
| Categories of people | (a) Users (account holders). (b) **Third parties**: recruiters, landlords, agencies — contacts and email correspondents. |
| Categories of data | Identity (name, email, phone). Application content (tracker rows). **special-adjacent documents** (employment contracts, payslips, tax notices, guarantor documents — financial/employment data). Mailbox content (threads the app sent + replies). Document text. Model inputs/outputs. |
| Recipients / processors | Hosting (Hetzner staging, AWS production). Model provider Mistral (ADR 0008 — DPA, no-training terms). Google/Microsoft as *data sources* for the user's own mailbox (user-consented OAuth). |
| Retention | Per category, section 4. |

## 2. Necessity and proportionality

- Tracker rows, contacts: necessary for the product. Minimal fields (naming table). Contacts limited to what a listing page publishes for contact purposes — never inferred addresses (enforced: contact email must appear verbatim in page text or be dropped).
- Documents: types limited by template. Encrypted at rest (envelope, ADR 0001). Downloads ownership-checked per request.
- Mailbox: data minimization hard-guaranteed — worker reads only threads the app sent + narrow contact-address fallback. Test fails on any out-of-scope read. Sending limits (daily cap, 7-day rule) protect both the user and third parties from spam.
- Model: only eligible document types (ADR 0009) + project description. Minimal context per task. Prompts never logged. Outputs are proposals, never actions.

## 3. Risks and measures

| Risk | Likelihood | Severity | Measures |
|---|---|---|---|
| Third-party data over-collection (contacts, mailbox) | medium | medium | Minimization rules above. Retention per category. Contacts rationale documented in naming table. |
| Sensitive documents leak to model provider | low | high | Eligibility policy in domain layer + gateway-not-called test (ADR 0009). Mistral terms/DPA (ADR 0008). |
| Document/tokens exfiltration from storage or DB | low | high | Envelope encryption (KMS in prod). Tokens never in browser. No presigned URLs. Secrets from env/secret store. |
| SSRF via link analysis against internal network | medium | high | Full SSRF suite (private/link-local/reserved ranges both IP versions, IP-pinned connections, redirect re-checks, size/timeout caps, HTML-only, per-user rate limit). |
| Spam / sender-reputation harm from the mail assistant | medium | medium | Explicit per-email approval only. Daily cap. 7-day rule. Provider limits. |
| Prompt injection from listings/emails | medium | medium | Output never executed/rendered as HTML. Proposals only. Grounding validation. |
| Account compromise | low | high | Better Auth cookies (httpOnly/Secure/SameSite), short-lived JWTs, rate limiting, strict CSP, IDOR tests. |
| Excessive retention | medium | medium | Purge jobs per category. Reconcile verifies convergence. |

Residual risk: acceptable for a single-owner certification project with test accounts in staging.

## 4. Retention (defaults. Purge jobs enforce)

| Category | Default |
|---|---|
| Tracker data, contacts, mail templates | life of project. Deleted with project (soft → purge) |
| Documents | life of project + 30 days after project deletion |
| Extracted document text (`document_texts`) | regenerated on demand. Purged with document |
| Email content (`email_contents`, Postgres table) | life of project. Message metadata kept until account deletion |
| Link analysis contents | 90 days |
| Mailbox tokens | until disconnect |
| Audit events | 12 months |
| Account (all stores) | deleted on request, cascade per ADR 0006. Export available first |

## 5. Rights

Access/export (JSON + files), rectification (edit everywhere in-app), erasure (account deletion cascade), withdrawal of consent (mailbox connection, model processing of documents) — each with immediate effect and audit trail. Legal notice + privacy policy pages list processors, data sources, and the Google Limited Use disclosure. No consent banner: only essential cookies (session) — documented.

## 6. Open points (phase 10)

- Confirm retention defaults with owner.
- CNIL-referenced DPIA template formatting for the jury copy (French).
- Record model provider sub-processor list snapshot date.
