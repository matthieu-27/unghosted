/** Tracker stats derivation: the numbers behind the workspace cards and
 * chart. Pure over the tracker payload — no component, no fetch. */

import type { ColumnDefinition, TrackerRow } from './tracker-types';

export interface DistributionEntry {
  key: string;
  label: string;
  count: number;
  color: string | null;
}

export interface Distribution {
  column: ColumnDefinition | undefined;
  entries: DistributionEntry[];
}

/** Counts of every option of the FIRST select column, zeros included,
 * biggest first (ties keep the definition order). The first select column
 * is the tracker's status-like axis by template convention. */
export function distribution(
  columns: ColumnDefinition[],
  rows: TrackerRow[],
): Distribution {
  const column = columns.find((candidate) => candidate.type === 'select');
  if (!column?.options) return { column: undefined, entries: [] };

  const counts = new Map(column.options.map((option) => [option.key, 0]));
  for (const row of rows) {
    const value = row.cells[column.key];
    if (typeof value === 'string' && counts.has(value)) {
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
  }
  return {
    column,
    entries: column.options
      .map((option) => ({
        key: option.key,
        label: option.label,
        count: counts.get(option.key) ?? 0,
        color: option.color ?? null,
      }))
      .sort((a, b) => b.count - a.count),
  };
}

/** Filled editable cells over all editable cells. System and computed
 * columns never count; a blank string is as empty as a missing value. */
export function fillRate(
  columns: ColumnDefinition[],
  rows: TrackerRow[],
): { filled: number; total: number } {
  const editable = columns.filter(
    (column) => !column.system && !column.computed,
  );
  let filled = 0;
  for (const row of rows) {
    for (const column of editable) {
      const value = row.cells[column.key];
      if (value !== null && value !== undefined && value !== '') filled += 1;
    }
  }
  return { filled, total: editable.length * rows.length };
}
