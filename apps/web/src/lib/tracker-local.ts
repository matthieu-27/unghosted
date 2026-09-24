/**
 * Pure local application of tracker operations (optimistic updates).
 * Mirrors the server semantics for the three MVP op kinds; ids assigned
 * optimistically (`tmp-…`) are replaced by server ids after the post-flush
 * refetch, which is why every successful flush invalidates the tracker query.
 */

import type { TrackerOperation, TrackerRow } from '@/lib/tracker-types';

let tmpCounter = 0;

function nextTempRowId(): string {
  tmpCounter += 1;
  return `tmp-${tmpCounter}`;
}

export function applyLocal(
  rows: TrackerRow[],
  operation: TrackerOperation,
): TrackerRow[] {
  if (operation.op === 'set_cell') {
    return rows.map((row) => {
      if (row.id !== operation.row_id) return row;
      const cells = { ...row.cells };
      if (operation.value == null) {
        delete cells[operation.column_key];
      } else {
        cells[operation.column_key] = operation.value;
      }
      return { ...row, cells };
    });
  }
  if (operation.op === 'insert_rows') {
    const fresh: TrackerRow[] = Array.from({ length: operation.count }, () => ({
      id: nextTempRowId(),
      order_key: nextTempRowId(), // order resolved server-side; refetch reorders
      cells: {},
    }));
    if (!operation.after_row_id) {
      return [...rows, ...fresh];
    }
    const index = rows.findIndex((row) => row.id === operation.after_row_id);
    if (index === -1) return [...rows, ...fresh];
    return [...rows.slice(0, index + 1), ...fresh, ...rows.slice(index + 1)];
  }
  // delete_rows
  const doomed = new Set(operation.row_ids);
  return rows.filter((row) => !doomed.has(row.id));
}
