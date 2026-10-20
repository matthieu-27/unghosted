/** Cell bar: selected cell address + value, like a formula bar minus formulas. */

import type { ColumnDefinition, TrackerRow } from '@/lib/tracker-types';

interface CellBarProps {
  column: ColumnDefinition | undefined;
  columnIndex: number;
  row: TrackerRow | undefined;
  rowIndex: number;
}

/** Spreadsheet-style column letters: 0=A, 1=B, 26=AA. */
export function columnLetter(index: number): string {
  let letter = '';
  let n = index;
  while (n >= 0) {
    letter = String.fromCharCode((n % 26) + 65) + letter;
    n = Math.floor(n / 26) - 1;
  }
  return letter;
}

function cellText(value: unknown): string {
  return value == null ? '' : String(value);
}

export function CellBar({ column, columnIndex, row, rowIndex }: CellBarProps) {
  const selected = column !== undefined && row !== undefined;
  const address = selected
    ? `${columnLetter(columnIndex)}${rowIndex + 1}`
    : '—';
  const value = selected ? row.cells[column.key] : undefined;
  return (
    <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border bg-card px-2 py-1 text-sm shadow-xs">
      <span className="w-9 shrink-0 rounded bg-muted px-1 text-center font-mono text-xs text-muted-foreground">
        {address}
      </span>
      <span className="truncate text-muted-foreground">
        {cellText(value) || 'Select a cell'}
      </span>
    </div>
  );
}
