# @unghosted/shared

Data shared between the web app and the Python API/backend worker:

- `templates/` — versioned project-template definitions (job search, rental
  search, property purchase). Data, not code: adding a template requires no
  code change. Lands in phase 1/3.
- `source-detection.json` — URL-domain to source-label mapping used by both
  the API (authoritative) and the web app (instant feedback). Phase 4.
- `schemas/` — JSON Schemas for API contracts. Phase 1+.

Plain JSON files, no build step. The web app imports them at build time; the
API reads them from disk. Nothing here is a browser public asset.
