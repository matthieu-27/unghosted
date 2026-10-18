# Tracker template definitions — phase 1 design

Templates are data: versioned JSON in `packages/shared/templates/`, seeded into Mongo at project creation. Adding a template requires no code change. This document is the source the JSON files will be generated from.

## Common project settings (both templates)

| Key | Type | Purpose |
|---|---|---|
| `default_mailbox_id` | uuid, optional | default sending mailbox. Empty until one is connected |
| `max_applications_per_day` | integer, default 10 | daily cap on first-contact emails sent from the project |

## `apprenticeship-search`

Work-study/apprenticeship search. Base: the "Le Dojo Club" spreadsheet model, extended.

### Project settings

| Key | Type | Purpose |
|---|---|---|
| `contract_end_date` | date | current contract end. statistics band shows countdown |
| `no_response_threshold_days` | integer, default 21 | past threshold + status Sent/Followed up + no human reply → suggestion to mark No response (never automatic) |

### Columns

| Key | Type | Notes |
|---|---|---|
| `date_sent` | date | |
| `company` | text | |
| `position` | text | |
| `listing_url` | url | |
| `location` | text | |
| `work_mode` | select | `on_site`, `hybrid`, `remote` |
| `contract_type` | select | `permanent`, `fixed_term`, `work_study`, `internship`, `freelance`, `temp`, `vie`.`work_study` first in list |
| `source` | select | see source mapping |
| `status` | select | see statuses |
| `last_contact` | date | |
| `response_date` | date | system-managed |
| `reply_type` | select | system-managed.`auto`, `human` |
| `next_action` | text | |
| `next_action_date` | date | |
| `follow_ups` | number | count of follow-ups sent |
| `contact` | contact-link | one or more project contacts |
| `salary_range_advertised` | text | as published |
| `salary_offered` | currency | gross annual, € |
| `cv` | document-link | CV version sent |
| `customised_letter` | document-link | generated customised letter sent |
| `interest` | rating | 1–5 |
| `notes` | long-text | extraction summary lands here |
| `days_since_sent` | computed | today − `date_sent`, read-only |

### Statuses and colors

Color never appears alone: each status renders color + icon + label.

| Key | Label | Color bucket |
|---|---|---|
| `to_apply` | To apply | none |
| `sent` | Sent | none |
| `followed_up` | Followed up | none |
| `hr_interview` | HR interview | blue |
| `technical_interview` | Technical interview | blue |
| `case_study` | Étude de cas | blue |
| `final_interview` | Final interview | blue |
| `offer` | Offer | green |
| `accepted` | Accepted | green |
| `rejected` | Rejected | red |
| `declined` | Declined | grey |
| `no_response` | No response | grey |
| `position_closed` | Position closed | grey |

### Conditional formatting rules

| Rule | Condition | Effect |
|---|---|---|
| interview | `status` in any interview status, `case_study`, `assessment`-equivalents | blue fill |
| success | `status` = `offer` or `accepted` | green fill |
| failure | `status` = `rejected` | red fill |
| closed | `status` in `no_response`, `position_closed` | grey fill |
| overdue-follow-up | `next_action_date` < today AND `status` in `sent`, `followed_up` AND no human reply | orange fill + clock icon |

Rules are declarative JSON.`overdue-follow-up` references reply state, proving rules can query row + reply data, not just row cells.

### Statistics

| Key | Definition |
|---|---|
| `applications_sent` | rows with status ≠ `to_apply` |
| `interviews` | rows that reached any interview status or later (offer, accepted, rejected after interview…) |
| `offers` | rows with `offer` or `accepted` |
| `response_rate` | rows with human reply OR status in {interviews, `offer`, `accepted`, `rejected`, `declined`} ÷ rows sent |
| `auto_reply_rate` | rows with reply_type `auto` ÷ rows sent |
| `avg_human_response_delay` | mean(response date − date sent) over human replies |
| `source_conversion` | interviews ÷ sent, grouped by source |

**Auto-replies never count as responses** (brief §3.1). Regression tests must prove impossible: counting `rejected` as non-response. A status missing from the status breakdown. A source missing from the source breakdown. An auto-reply counting as a response.

### Document types

Uploads are PDF-only, 3 MB per file. `cv`, `motivation_letter` (generic uploads), `generated_customised_letter` (per-application output) are eligible.`employment_contract`, `payslip`, `tax_notice`, `id_document`, `guarantor_document`, `bank_details`, `other` are never eligible. Flags in ADR 0009.

### Default mail templates

| Key | Purpose |
|---|---|
| `follow-up-application` | follow-up after application sent |
| `thank-you-interview` | thank-you after interview |
| `follow-up-interview` | follow-up after interview |

### Analysis hints

Per page kind (`job_offer`, `company`, `careers`, `school_program`, `agency`, `other`): fields to look for = position, company, contract type, location, salary, work mode, summary. Contact addresses only if verbatim on page.

## `rental-search`

### Project settings

| Key | Type | Purpose |
|---|---|---|
| `max_budget_rent` | currency | rent incl. charges. Referenced by conditional rule |
| `target_area` | text | free text |
| `target_move_in_date` | date | |

### Columns

| Key | Type | Notes |
|---|---|---|
| `date_added` | date | |
| `listing` | url | |
| `source` | select | auto-detected from domain, editable |
| `property` | text | free label, e.g. "2-room 45 m², Montreuil" |
| `address` | text | free text, may be partial |
| `rent_incl_charges` | currency | |
| `contacted` | checkbox | |
| `application_sent` | checkbox | |
| `status` | select | see statuses |
| `follow_up_date` | date | |
| `contact` | contact-link | agency or landlord |
| `response_date` | date | system-managed |
| `reply_type` | select | system-managed |
| `notes` | long-text | |

### Statuses and colors

| Key | Label | Color bucket |
|---|---|---|
| `spotted` | Spotted | none |
| `awaiting_reply` | Awaiting reply | none |
| `visit_scheduled` | Visit scheduled | blue |
| `visited` | Visited | blue |
| `accepted` | Accepted | green |
| `rejected` | Rejected | red |
| `listing_removed` | Listing removed | grey |
| `dropped` | Dropped | grey |

### Conditional formatting rules

| Rule | Condition | Effect |
|---|---|---|
| visit | `status` in `visit_scheduled`, `visited` | blue fill |
| success | `status` = `accepted` | green fill |
| failure | `status` = `rejected` | red fill |
| closed | `status` in `listing_removed`, `dropped` | grey fill |
| overdue-follow-up | `follow_up_date` < today AND `status` in `spotted`, `awaiting_reply` AND no human reply | orange fill + clock icon |
| over-budget | `rent_incl_charges` > project setting `max_budget_rent` | red cell + warning icon (references project settings) |

### Statistics

| Key | Definition |
|---|---|
| `listings_tracked` | all rows |
| `contacted` | `contacted` = true |
| `applications_sent` | `application_sent` = true |
| `response_rate` | human replies ÷ contacted |
| `auto_reply_rate` | auto replies ÷ contacted |

### Document types

`housing_file` (eligible — feeds applicant profile).`tax_notice`, `payslip`, `id_document`, `guarantor_document`, `bank_details`, `employment_contract`, `other` (never eligible). No CV, no letters.

### Default mail templates

| Key | Purpose |
|---|---|
| `visit-request` | ask for a visit slot |
| `follow-up-file` | follow-up after sending the housing file |

## Source detection mapping (`packages/shared/source-domains.json`)

Detection from URL domain only, no fetch. Subdomains (`www.`, `m.`) and malformed URLs handled. Unknown domain → `other` + keeps domain for display. One shared file, authoritative in API, mirrored in web for instant feedback.

| Domain | Source |
|---|---|
| `linkedin.com` | `linkedin` |
| `welcometothejungle.com` | `wttj` |
| `indeed.com` | `indeed` |
| `francetravail.fr` | `france_travail` |
| `apec.fr` | `apec` |
| `hellowork.com` | `hellowork` |
| `seloger.com` | `seloger` |
| `leboncoin.fr` | `leboncoin` |
| `pap.fr` | `pap` |
| `bienici.com` | `bienici` |
| `logic-immo.com` | `logic_immo` |
| `locservice.fr` | `loc_service` |

Plus non-domain sources present only as select options: `company_website`, `referral`, `recruitment_agency`, `spontaneous`, `school_job_board`, `internal`, `other`.

## System-managed columns (both templates)

`response_date` and `reply_type` are written only through the operations path by the reply worker (system author). Semantics (brief §3.5):

- `response_date` = date of first reply of any kind in the thread, auto-replies included.
- `reply_type` = `auto` or `human`. Upgrades `auto` → `human` when a human reply arrives later.`response_date` stays at the first reply.
- Manual corrections are logged in `audit_events` and never overwritten by the worker.
