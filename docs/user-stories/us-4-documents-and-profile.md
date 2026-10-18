# 4 — Documents and applicant profile

[← All user stories](./README.md)

1. **Upload.** AC: PDF-only, 3 MB per file. Type assigned at upload from template list (`cv` and `motivation_letter` for apprenticeship, `housing_file` for rental). Content sniffed. Storage key renamed. Never rendered inline from app origin.
2. **Eligibility enforced.** AC: ineligible types (`id_document`, `tax_notice`, `payslip`, `bank_details`, `guarantor_document`) never reach the model gateway — proven by a test asserting the gateway isn't called.
3. **Profile draft.** AC: model reads eligible docs + project description only. Draft has headline, highlights with stable ids, motivation, style notes, availability. User edits and approves. Regenerating never overwrites the approved version.
4. **Download.** AC: streamed through API with ownership check. Decrypted server-side. No presigned URLs.
5. **Consent.** AC: separate consent screens for mailbox connection and model processing of documents. Withdrawal honored.
