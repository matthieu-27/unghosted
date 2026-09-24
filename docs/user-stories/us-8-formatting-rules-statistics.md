# 8 — Formatting, rules, statistics

[← All user stories](./README.md)

1. **Sparse styles.** AC: bold/italic/underline/strike, colors, alignment, wrap, number format stored only for cells differing from defaults.
2. **Conditional formatting.** AC: template rules render per `docs/tracker-templates.md`. Rules referencing project settings (over-budget) update when settings change. Status never conveyed by color alone (icon + label).
3. **statistics band.** AC: template-defined statistics computed client-side from rows. Regression tests from brief §3.1 pass (auto-reply never counts as response, no missing status/source bucket).
4. **Source detection.** AC: domain → source without fetching. Subdomains handled. Unknown → `other` with domain kept. User override sticks.
5. **Find & replace, sort, filter, remove duplicates.** AC: all operate on typed values. Remove duplicates previews matches before deleting.
