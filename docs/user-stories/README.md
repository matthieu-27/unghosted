# User stories

Actor is the user (owner). Referenced by section and item. Acceptance criterias are testable. Numbering follows `docs/mvp.md`: stories 1-5 are the MVP in build order, 6-12 are post-MVP in value order. MVP-only view of the stories: [`mvp.md`](./mvp.md).

1. [Projects](./us-1-projects.md) — **MVP** (M1)
2. [Tracker editing](./us-2-tracker-editing.md) — **MVP** (M1)
3. [Link analysis ("+ New application")](./us-3-link-analysis.md) — **MVP** (M2)
4. [Documents and applicant profile](./us-4-documents-and-profile.md) — **MVP** (M3)
5. [Mailbox and sending](./us-5-mailbox-and-sending.md) — **MVP** (M4), except item 1 (OAuth mailboxes, post-MVP). MVP sends through Mailpit over SMTP
6. [Authentication and account](./us-6-authentication-and-account.md) — post-MVP
7. [Contacts](./us-7-contacts.md) — post-MVP
8. [Formatting, rules, statistics](./us-8-formatting-rules-statistics.md) — post-MVP
9. [Manual mail](./us-9-manual-mail.md) — post-MVP
10. [Replies and follow-ups](./us-10-replies-and-follow-ups.md) — post-MVP
11. [Exports](./us-11-exports.md) — post-MVP
12. [GDPR](./us-12-gdpr.md) — post-MVP

## NFR (cross-cutting, tested)

- Accessibility: keyboard operation everywhere. Visible focus. Contrast light/dark. Axe checks in Playwright on every main screen.
- Security: owner-only authorization on every resource (IDOR tests). Strict CSP. CSRF on cookie routes. Strict CORS. Secrets from env only.
- Eco-design: virtualization, lazy routes, bundle budget in CI, debounced autosave, no polling, deterministic before model, extraction cache per URL, compressed responses.
