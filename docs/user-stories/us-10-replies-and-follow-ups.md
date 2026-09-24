# 10 — Replies and follow-ups

[← All user stories](./README.md)

1. **Sync scope.** AC: worker reads only threads the app sent + narrow contact-address fallback. Fake provider fails test on any out-of-scope read.
2. **Reply typing.** AC: headers first (`Auto-Submitted`, `X-Autoreply`, `X-Autorespond`, `Precedence`). Model only when inconclusive.
3. **Automatic fields.** AC: response date + reply type written via operations path without confirmation. `auto` upgrades to `human`. Manual corrections logged and never overwritten. Auto-reply sets response date but not response-rate statistics.
4. **Status proposals.** AC: human reply produces a suggestion (e.g. rejection, interview) with justification. Shown in Mail inbox and on row. Never applied automatically.
5. **Follow-up drafting.** AC: proposed in-thread, aware of elapsed time. User edits + approves. Overdue rows surfaced.
6. **Template proposals.** AC: model may propose new follow-up templates from sent emails + outcomes. Save/edit/discard each.
