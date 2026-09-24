# MVP scope

Decided 2026-09-21. The dossier needs a shipped, demoable product first. This document overlays the roadmap: user stories and ADRs stay valid, the MVP tags in `docs/user-stories/README.md` say what ships first.

## In / out

| In the MVP | Deferred (post-MVP) |
|---|---|
| Projects CRUD, both templates, dashboard | Authentication (seeded single user. Schema keeps `owner_user_id`, so auth lands later without migration pain) |
| Tracker grid: typed columns, editing, keyboard navigation, virtualization, autosave + revision conflicts | Contacts (first-contact recipient typed manually, pre-filled from extraction) |
| "+ New application": paste, SSRF-guarded fetch, page kind, extraction, review form | Statistics band |
| Documents: PDF upload, tagging, eligibility policy | Conditional-formatting engine (statuses keep their static template colors) |
| Applicant profile: draft, edit, approve | Toolbar cell formatting (sparse styles) |
| Customised letter + first-contact email + attachments + sending | Mail templates management, "mark as sent" flows |
| Sending limits enforced in the domain layer | OAuth mailboxes (Gmail/Outlook), reply worker, follow-ups, proposals |
| | Exports, GDPR features, version history (already cut), staging deploy |

Autosave stays — a tracker that loses data on refresh isn't a product.

## Temporary mailing: Mailpit

Sending runs through the mail gateway with an **SMTP implementation** targeting [Mailpit](https://mailpit.axllent.org) (SMTP catcher in docker-compose, web inbox on port 8025). This exercises the whole pipeline — draft, approve, attachments, send, thread/message recording, audit — with zero OAuth or provider-verification overhead, and gives the jury a visible inbox during the demo.

The gmail and graph gateway implementations replace it post-MVP without touching the pipeline (same interface, configuration-selected).

## Build order

Each slice is demoable on its own.

| Slice | Ships | Demo |
|---|---|---|
| **M1** | projects + editable tracker + autosave | create a project from each template, edit cells, reload, data survives, 409 on stale revision |
| **M2** | "+ New application" paste flow | paste a job offer link and a housing listing link, watch the pre-filled review form, save the row |
| **M3** | documents + applicant profile | upload CV + motivation letter, approve a drafted profile, watch ineligible types bounce off the model gateway |
| **M4** | customised letter + first-contact + send | draft from a row, edit, attach CV + letter, send, read it in the Mailpit inbox, see the row update |

## Post-MVP order (value order)

1. Authentication (Better Auth + JWT)
2. Contacts
3. Statistics band + conditional-formatting engine
4. OAuth mailboxes + real provider sending
5. Reply worker + follow-ups + proposals
6. Exports
7. GDPR features
8. Staging (Hetzner) then production (AWS)

## Consequences

- The tracker data model (ADR 0005), fetch safety, eligibility policy, and consistency flows (ADR 0006) are all exercised by the MVP — nothing built now is throwaway.
- The reply worker's automatic fields land post-MVP with the real mailboxes.
- Phase docs (brief §11) remain the long-form roadmap. This file is the build order.
