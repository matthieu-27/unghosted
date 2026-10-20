/** Tracker stats derivation (us polish pass): pure functions over the
 * tracker payload, so the numbers the cards and chart show are testable
 * without rendering. */

import { describe, expect, it } from 'vitest';
import { distribution, fillRate } from './tracker-stats';
import type { ColumnDefinition, TrackerRow } from './tracker-types';

const status: ColumnDefinition = {
  key: 'status',
  type: 'select',
  label: 'Status',
  options: [
    { key: 'sent', label: 'Sent', color: '#0ea5e9' },
    { key: 'replied', label: 'Replied', color: '#22c55e' },
    { key: 'ghosted', label: 'Ghosted', color: '#f43f5e' },
  ],
};
const company: ColumnDefinition = {
  key: 'company',
  type: 'text',
  label: 'Company',
};
const created: ColumnDefinition = {
  key: 'created_at',
  type: 'date',
  label: 'Created',
  system: true,
};

const rows: TrackerRow[] = [
  {
    id: 'r1',
    order_key: 'r1',
    cells: { status: 'sent', company: 'Le Dojo Club' },
  },
  { id: 'r2', order_key: 'r2', cells: { status: 'sent', company: '' } },
  { id: 'r3', order_key: 'r3', cells: { status: 'ghosted' } },
];

describe('distribution', () => {
  it('counts every option of the first select column, zeros included', () => {
    const result = distribution([company, status], rows);
    expect(result.column?.key).toBe('status');
    expect(result.entries).toEqual([
      { key: 'sent', label: 'Sent', count: 2, color: '#0ea5e9' },
      { key: 'ghosted', label: 'Ghosted', count: 1, color: '#f43f5e' },
      { key: 'replied', label: 'Replied', count: 0, color: '#22c55e' },
    ]);
  });

  it('reports no column when the tracker has no select column', () => {
    expect(distribution([company], rows).column).toBeUndefined();
    expect(distribution([company], rows).entries).toEqual([]);
  });

  it('ignores cell values that are not defined options', () => {
    const odd: TrackerRow[] = [
      { id: 'r9', order_key: 'r9', cells: { status: 'made-up' } },
    ];
    const result = distribution([status], odd);
    expect(result.entries.map((entry) => entry.count)).toEqual([0, 0, 0]);
  });
});

describe('fillRate', () => {
  it('counts filled editable cells, ignoring system columns and blanks', () => {
    // Editable cells: status (3 filled) + company (r1 filled, r2 blank, r3
    // missing) = 4 of 6. The system date column never counts.
    expect(fillRate([status, company, created], rows)).toEqual({
      filled: 4,
      total: 6,
    });
  });

  it('returns a zero total when there is nothing editable', () => {
    expect(fillRate([created], rows)).toEqual({ filled: 0, total: 0 });
  });
});
