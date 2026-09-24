# ADR 0003 — TanStack stack and typed URL state

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

Phase 0 verified on Bun 1.3.12: TanStack Start dev/build/production with SSR, Better Auth mounted on server routes, shadcn (Base UI) components installable. The brief (§4.2b) prescribes the TanStack stack and typed, validated URL state so every view is linkable and survives reload.

## Decision

- **TanStack Start** for SSR (landing), server routes (Better Auth), app shell. No business logic in Start server functions — the Python API is the only back end for business data.
- **TanStack Router**, file-based typed routes (see naming table for route files).
- **URL state is typed and validated** with router search-param validation: current project (path param), left-rail section (path param), tracker sort/filters/selection (search params), open modals (search params). Every workspace view is deep-linkable.
- **TanStack Query** for all server state. Conventions: query keys are arrays rooted by resource (`['projects', id, 'tracker']`). Mutations for autosave operations and sends. Optimistic updates only where rollback is well defined (cell edits yes, sending emails never). Invalidation after mutations. Refetch on window focus to pick up reply worker changes — no interval polling (eco-design).
- **TanStack Table + TanStack Virtual** for the grid (ADR 0004), **TanStack Form** for the New project modal, the "+ New application" review form, contacts, and the email editor, with validation schemas derived from the same shared JSON Schemas as the API.
- JWT handling confined to one API client module.

## Alternatives considered

React Router v7 framework mode — fallback if Start had failed phase 0 checks. It didn't.

## Consequences

- One vendor family for router/query/table/form: shared idioms, one upgrade path.
- URL-as-state means the back button and sharing links behave correctly everywhere. It also means search-param schemas must be maintained as features are added.
- Bundle budget checks in CI keep the stack honest (eco-design §8.4).
