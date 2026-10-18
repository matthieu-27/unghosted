# 3 — Link analysis ("+ New application")

[← All user stories](./README.md)

1. **One paste.** AC: single input accepts URL or pasted text, auto-detected. "Fill manually" opens plain form from column definitions, no model.
2. **Fetch safety.** AC: SSRF suite passes — only http/https default ports. DNS resolved and private/loopback/link-local/reserved IPv4+IPv6 blocked (incl. `169.254.169.254`). Connect to checked IP. Capped redirects re-checked. Size + timeout caps. HTML content types only. No JS. Per-user rate limit.
3. **Page kind.** AC: deterministic first (JSON-LD, OpenGraph, URL patterns). Model only when inconclusive, with confidence. Kinds from shared config.
4. **Extraction.** AC: structured data fills first. Model fills the rest with schema generated from tracker columns. Invalid fields dropped not fatal. Contact addresses verbatim or dropped. Field-level provenance returned (structured / meta / model / detection).
5. **Review form.** AC: page kind shown and editable (re-runs extraction). Auto-filled markers. Duplicate URL warning. Kind/project mismatch warning with continue/cancel. Nothing saved until confirmed. "Write first contact" offered after save.
