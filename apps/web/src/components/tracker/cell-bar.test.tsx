import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { CellBar, columnLetter } from '@/components/tracker/cell-bar';
import type { ColumnDefinition, TrackerRow } from '@/lib/tracker-types';

afterEach(cleanup);

const column: ColumnDefinition = {
  key: 'company',
  label: 'Company',
  type: 'text',
};

const row: TrackerRow = {
  id: 'row-1',
  order_key: 'a',
  cells: { company: 'Acme' },
};

describe('columnLetter', () => {
  it('user sees A for column 0 and Z for column 25', () => {
    expect(columnLetter(0)).toBe('A');
    expect(columnLetter(25)).toBe('Z');
  });

  it('user sees AA for column 26 and AB for column 27', () => {
    expect(columnLetter(26)).toBe('AA');
    expect(columnLetter(27)).toBe('AB');
  });
});

describe('CellBar', () => {
  it('user sees selected cell address and value', () => {
    render(<CellBar column={column} columnIndex={1} row={row} rowIndex={0} />);
    expect(screen.getByText('B1')).toBeTruthy();
    expect(screen.getByText('Acme')).toBeTruthy();
  });

  it('user sees em dash when no cell is selected', () => {
    render(
      <CellBar
        column={undefined}
        columnIndex={0}
        row={undefined}
        rowIndex={0}
      />,
    );
    expect(screen.getByText('—')).toBeTruthy();
  });

  it('user sees blank text for null cell value', () => {
    const emptyRow: TrackerRow = { ...row, cells: {} };
    render(
      <CellBar column={column} columnIndex={0} row={emptyRow} rowIndex={2} />,
    );
    expect(screen.getByText('A3')).toBeTruthy();
  });
});
