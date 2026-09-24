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
    <div className="flex items-center gap-2 border px-2 py-1 text-sm">
      <span className="w-10 shrink-0 text-muted-foreground">{address}</span>
      <span className="truncate">{cellText(value)}</span>
    </div>
  );
}
