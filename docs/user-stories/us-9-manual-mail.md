# 9 — Manual mail (no mailbox)

[← All user stories](./README.md)

1. **Templates.** AC: seeded defaults per template. Placeholders `{{company}}`, `{{position}}`, `{{contact.name}}`, `{{date_sent}}`, `{{listing}}` resolve from row + contact. Unknown placeholder left visible with warning.
2. **Draft from row.** AC: without a connected mailbox, drafts are offered for copy or `mailto:`. Send disabled with explanation.
3. **Mark as sent.** AC: increments `follow_ups`, sets `last_contact`, suggests next follow-up date. Row changes only after user confirmation.
