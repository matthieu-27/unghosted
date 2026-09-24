# ADR 0004 — Tracker grid: The shadcn Data Table recipe on TanStack Table v9

- Status: accepted (phase 1)
- Date: 2026-09-21

## Context

The brief (§2.5) starts from the shadcn Data Table recipe (TanStack Table) and asks which major version the current recipe targets, since Table v9 is out.

## Findings (checked 2026-09-21)

- TanStack Table v9 is stable and current (packages at 9.2.x. Migration guide in the repo).
- The current shadcn data-table recipe (base and aria variants) is written **for v9**: `useTable`, `tableFeatures({..})` with explicit feature registration (tree-shaking), feature-scoped row models and sort/filter functions (ui.shadcn.com/docs/components/base/data-table).

## Options

1. **v8 recipe heritage.** v8 docs and community examples are abundant, but v8 is the previous major. Starting a new project on it buys a migration later. Rejected.
2. **v9 + shadcn v9 recipe.** Recipe matches the shipped major, feature registration trims bundle (eco-design), and the recipe's composed components (Table/Toolbar/ColumnHeader) extend into an editable grid. Chosen.

## Decision

Build the tracker grid on **@tanstack/react-table v9**, extending the shadcn recipe:

- in-cell editing with type-appropriate editors per column type (naming table, tracker-templates.md).
- single-cell and range selection. Keyboard navigation per the WAI-ARIA grid pattern (arrows, Tab, Enter, Escape, Home/End, Ctrl+arrows).
- copy/paste as tab-separated text.
- row virtualization with **TanStack Virtual**.
- column resize/reorder, sticky header, freeze panes.
- edits batch into operations (ADR 0005 carries the persistence side).

## Consequences

- Fewer third-party examples for the editable-grid edge cases than v8 has. The recipe's structure is the anchor.
- Feature registration must be maintained — a feature used but not registered fails visibly (good failure mode).
- Accessibility testing (axe + keyboard scripts) is part of phase 3/4 acceptance.
