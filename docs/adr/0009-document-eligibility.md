# ADR 0009 — Document eligibility: What the model may ever read

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

Applicants upload identity, financial, and employment documents next to CVs and letters. The model needs some of them (profile drafting, letter grounding) and must never see others (brief §2.8). The rule is enforced in the domain layer, not the UI, and covered by a test asserting the model gateway isn't called.

## Default eligibility list

| Type key | Eligible | Rationale |
|---|---|---|
| `cv` | yes | profile highlights are drawn from it |
| `motivation_letter` | yes | the user's generic letter. Motivation + style notes come from it |
| `generated_customised_letter` | yes | already model-generated content |
| `housing_file` | yes | rental profile (situation, timing, guarantee type) is drafted from it |
| `employment_contract` | no | financial/employment terms. Not needed for any task |
| `payslip` | no | financial data. The profile states situation in general terms, without figures |
| `tax_notice` | no | financial data |
| `id_document` | no | identity document. No task needs it |
| `guarantor_document` | no | third-party personal data |
| `bank_details` | no | no task needs it |
| `other` | no | unknown content defaults to never |

Eligibility is defined per template (the JSON files) and **snapshotted onto each document row at upload** (`documents.model_eligible`), so a later template change never retroactively exposes old documents.

## Enforcement points

1. Upload: type key must exist in the project's template list. The snapshot flag is written.
2. Text extraction job: runs only for eligible documents — ineligible types never produce a `document_texts` row.
3. Every model-call service: resolves input documents and **rejects in the domain layer if any is ineligible** — raising before the gateway is touched.
4. Attachments are out of scope here: attaching a file to an email never sends it to the model. The editor also warns on sensitive attachment types.

## Consequences

- The unit test "ineligible document never reaches the model gateway" is the phase 7 acceptance gate.
- GDPR story stays simple: eligible set is the only personal content with a processor (Mistral, ADR 0008), listed in the privacy policy and the DPIA.
- Adding a new type means a template change + this table updated. The default is never eligible.
