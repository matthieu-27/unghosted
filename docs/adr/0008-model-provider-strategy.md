# ADR 0008 — Model provider strategy: Mistral (hosted) + Ollama (self-hosted) behind a gateway

- Status: accepted (phase 1. Self-hosted implementation gated on owner's compute answer)
- Date: 2026-09-21
- Terms verified: 2026-09-21

## Context

The model now processes personal data: CV text, applicant profiles, contact details, email content. Requirements (brief §6.3): provider terms must exclude training on inputs and offer a GDPR data-processing agreement, or be self-hosted. Gmail data is also in scope (Google Limited Use), so the same discipline applies everywhere.

## Providers evaluated

**Mistral AI — La Plateforme (chosen, hosted).** EU company (Paris), directly subject to GDPR.

<!-- vale Microsoft.Contractions = NO -->
<!-- vale Microsoft.Terms = NO -->
<!-- vale Microsoft.Quotes = NO -->
<!-- Suppressed on this line only: verbatim quotes from Mistral's terms — wording and punctuation stay as published. -->
- Commercial Terms of Service (legal.mistral.ai/terms/commercial-terms-of-service): **§4.1** — the license Mistral receives to operate the products "excludes model training". **§4.2** — "Mistral AI will not use Customer Data or Outputs to train its artificial intelligence models except" four carve-outs: (a) opt-in products, (b) Feedback (§2.4 — submitting feedback may carry associated data), (c) an Order Form saying otherwise, (d) **Labs and Preview models** (§4.3 — opt-outs don't apply).
<!-- vale Microsoft.Contractions = YES -->
<!-- vale Microsoft.Quotes = YES -->
<!-- vale Microsoft.Terms = YES -->
- Data Processing Addendum exists at legal.mistral.ai/terms/data-processing-addendum (incorporated via §12.3), enabling GDPR-compliant processing as a processor.
- API inputs/outputs: default retention for abuse monitoring with zero-data-retention available as an opt-out preference (per §4.3 references). Exact windows live in the DPA — re-verify at integration time (phase 6) and pin the version.

Operational guardrails from the carve-outs: **use paid API endpoints only, avoid `labs`/preview models, never submit Feedback with real data.**

**Ollama / llama.cpp with an Apache-2.0 model (chosen, self-hosted).** Terms trivially satisfied (no data leaves the machine). Implementation deferred until the owner answers the compute question (CPU-only vs GPU on AWS and the VPS) — per brief, ask before implementing.

Rejected: providers whose terms train on API inputs by default, and free tiers without a DPA.

## Decision

- A `model` gateway interface in `unghosted.gateways` with two implementations selected by configuration: `mistral` (hosted API) and `ollama` (self-hosted). Exact pinned versions recorded at integration (phase 6).
- The document-eligibility policy (ADR 0009) is enforced **before every model call**, in the domain layer, covered by tests.
- Minimal context per task. Logs record task type, provider, token counts, latency — never prompt content.
- Prompt-injection stance (brief §6.4): model output is never executed, never rendered as HTML, and can't trigger actions. It only creates proposals.

## Consequences

- Personal data stays within EU jurisdiction on the hosted path. The self-hosted path exists for full control.
- Model-version pinning + a small evaluation fixture set (brief §6.5) keep quality observable. Evaluation runs in CI.
- Terms re-check date: phase 6 start (Mistral terms cited above are the 2026-08-04 revision).

## References

- https://legal.mistral.ai/terms/commercial-terms-of-service (§2.4, §4.1, §4.2, §4.3, §11.4, §12.3)
- https://legal.mistral.ai/terms/data-processing-addendum
- https://docs.getmoto.org — moto (S3 mock, referenced by ADR 0001)
