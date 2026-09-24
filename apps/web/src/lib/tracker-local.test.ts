import { describe, expect, it } from 'vitest';

import { applyLocal } from './tracker-local';
import type { TrackerRow } from './tracker-types';

function row(id: string, cells: Record<string, unknown> = {}): TrackerRow {
  return { id, order_key: id, cells };
}

describe('applyLocal', () => {
  it('set_cell writes the value into the matching row only', () => {
    const rows = [row('a'), row('b')];
    const next = applyLocal(rows, {
      op: 'set_cell',
      row_id: 'a',
      column_key: 'company',
      value: 'Acme',
    });
    expect(next[0]?.cells.company).toBe('Acme');
    expect(next[1]?.cells.company).toBeUndefined();
    expect(rows[0]?.cells.company).toBeUndefined(); // input not mutated
  });

  it('set_cell with null clears the cell', () => {
    const rows = [row('a', { company: 'Acme' })];
    const next = applyLocal(rows, {
      op: 'set_cell',
      row_id: 'a',
      column_key: 'company',
      value: null,
    });
    expect(next[0]?.cells.company).toBeUndefined();
  });

  it('insert_rows appends temporary rows', () => {
    const next = applyLocal([row('a')], { op: 'insert_rows', count: 2 });
    expect(next).toHaveLength(3);
    expect(next[1]?.id).toMatch(/^tmp-/);
    expect(next[2]?.id).toMatch(/^tmp-/);
  });

  it('insert_rows after a specific row inserts right after it', () => {
    const next = applyLocal([row('a'), row('b')], {
      op: 'insert_rows',
      after_row_id: 'a',
      count: 1,
    });
    expect(next.map((r) => r.id)).toEqual([
      'a',
      expect.stringMatching(/^tmp-/),
      'b',
    ]);
  });

  it('delete_rows removes exactly the listed ids', () => {
    const next = applyLocal([row('a'), row('b'), row('c')], {
      op: 'delete_rows',
      row_ids: ['a', 'c'],
    });
    expect(next.map((r) => r.id)).toEqual(['b']);
  });

  it('delete_rows with unknown id leaves the list unchanged', () => {
    const next = applyLocal([row('a')], {
      op: 'delete_rows',
      row_ids: ['ghost'],
    });
    expect(next.map((r) => r.id)).toEqual(['a']);
  });
});
