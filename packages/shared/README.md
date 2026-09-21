# @unghosted/shared

Data shared between the web app and the Python API and worker (the back end):

- `templates/` — versioned project-template definitions (apprenticeship
  search, rental search). Data, not code: adding a template requires no
  code change.
- `source-domains.json` — URL-domain to source-label mapping used by both
  the API (authoritative) and the web app (instant feedback).
- `schemas/` — JSON Schemas for API contracts shared by both sides.

Plain JSON files, no build step. The web app imports them at build time. The
API reads them from disk. Nothing here is a browser public asset.
