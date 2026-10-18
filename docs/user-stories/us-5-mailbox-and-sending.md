# 5 — Mailbox and sending

[← All user stories](./README.md)

1. **Connect mailboxes.** AC: OAuth PKCE via API for Gmail and Outlook. One or more per user. Tokens encrypted (envelope) and never sent to browser. Disconnect revokes + deletes + stops sync. Projects using it fall back to no default.
2. **Customised letter (apprenticeship).** AC: drafted from approved profile + row + listing text, derived from the user's generic `motivation_letter`. Editor + approve. PDF via Playwright, French business-letter layout, one page with overflow warning. Stored as versioned `generated_customised_letter` linked to row. Language follows listing, user can override. The CV is attached as-is, never customized.
3. **First-contact email.** AC: short (3–5 sentences) when letter attached. Grounding — `used_highlights` ids exist in approved profile, no leftover placeholders, names match contact/company, language respected, no links except user's own. Editor shows relied-on facts and warnings. Without a connected mailbox, "Write first contact" is gated with an error toast pointing to `/account/mailboxes`.
4. **Attachments.** AC: template-suggested types pre-selected and visible. Sensitive types warned explicitly. Provider size limits enforced before Send (Graph: <3 MB direct, 3–150 MB upload session, ~35 MB message default). Sent documents recorded on message + audit.
5. **Send.** AC: one explicit click per email, no bulk, no scheduling. From selector defaults to project mailbox. Daily cap (default 10) and 7-day rule enforced in domain layer with timezone-boundary tests. Human-reply exception applies. Thread headers correct for follow-ups.
6. **Recording.** AC: provider message + thread ids stored. Final sent text + attachments stored (not the model proposal). `last_contact`, `date_sent`, `cv`, `customised_letter` updated after user sees what will change. Audit event.
