# CDA mapping — RNCP37873 competencies to evidence

Updated at the end of every phase. Feeds the *dossier de projet*.

| # | Competency | Phases | Evidence |
|---|---|---|---|
| 1 | Set up the work environment | 0 | Monorepo scaffold, Bun workspaces + uv, docker-compose (Postgres, Mongo), pre-commit gate (ruff, mypy --strict, biome, tsc, gitleaks), CI on GitHub Actions, `docs/ai/phase-0-compatibility-report.md` (TanStack Start on Bun, Better Auth integration, shadcn), README one-command setup |
| 2 | Develop user interfaces | 1, 2, 3, 4, 5, 6, 8 | Phase 1: Penpot wireframes. Later: landing, dashboard, workspace chrome, editable grid (ADR 0004), forms. M4: mail editor (draft, edit, attachments picker, approve/send, sent list, URL-held flow state). M5: landing, sign-up and sign-in forms, guarded layout with sign-out. A11y (RGAA, axe) |
| 3 | Develop business components | 3–9 | Domain layer (stats, conditional rules, source detection, eligibility, reply rules, operations), services, worker job handlers. M4: mail domain (daily cap per Europe/Paris day, 7-day recipient cooldown, 25 MB attachment cap) + mail service with server-recomputed grounding warnings. M5: JWT authentication middleware and the JWKS gateway (key caching, rotation, refresh rate limit) |
| 4 | Contribute to project management | all | Phase reports, user stories `docs/user-stories/`, ADR log, naming tables |
| 5 | Analyze needs and create mockups | 1 | User stories with acceptance criteria. Penpot wireframes for every screen |
| 6 | Define the software architecture | 1 | `docs/diagrams/architecture.puml`, ADRs 0001–0012, layered back end (api/services/domain/repositories/gateways) |
| 7 | Design and set up a relational database | 1, 3, 4 | MCD `mcd.puml`, MLD `mld.dbml`, physical Alembic migrations, least-privilege roles. M4: mail schema (drafts, threads, messages, audit events). M5: `auth` schema owned by Better Auth's own migrations, isolated from Alembic (ADR 0012) |
| 8 | Develop SQL and NoSQL data-access components | 3, 5, 6, 7, 9 | SQLAlchemy 2 repositories (Postgres), PyMongo async (Mongo document model `mongo-model.puml`), Postgres-backed job queue (ADR 0007), storage gateway (local + S3, ADR 0001), envelope-encrypted document storage with the row-then-object-then-text write order (ADR 0006) |
| 9 | Prepare and run test plans | 1, 3–10 | User-story acceptance criteria as test plan seed. Unit (domain regression suite incl. stats pitfalls), integration (cross-store consistency), e2e (Playwright + axe), security (IDOR, SSRF suite), model-eligibility acceptance gate asserting the gateway is never called for an ineligible document (ADR 0009), ML evaluation fixtures. M4: 21 mail domain unit tests, 11 mail API integration tests over gateway doubles (SMTP, PDF, model), 33 web mail vitest cases. M5: 20 token-rejection tests (expiry, nbf, tampering, foreign key, unknown/missing kid, wrong iss/aud, alg=none, non-UUID subject), a real two-user IDOR test, 16 web auth vitest cases. Phase 10 written plan + execution report |
| 10 | Prepare and document deployment | 2, 11 | Staging compose + TLS + backups on Hetzner (phase 2). AWS production infra, deployment guide, rollback (phase 11) |
| 11 | Contribute to production release with a DevOps approach | 2, 11 | CI/CD gating `main`, automatic deploys on merge, monitoring incl. queue health and sync lag, S3 smoke test in pipeline |
