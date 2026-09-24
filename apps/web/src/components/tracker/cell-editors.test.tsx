import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(cleanup);

import type { ColumnDefinition, TrackerRow } from '@/lib/tracker-types';
import { CellDisplay, CellEditor } from './cell-editors';

const row: TrackerRow = { id: 'r1', order_key: 'k', cells: {} };

describe('CellDisplay', () => {
  it('renders an em dash for empty values', () => {
    render(<CellDisplay column={textColumn()} row={row} />);
    expect(screen.getByText('—')).toBeTruthy();
  });

  it('renders the option label for select values', () => {
    render(
      <CellDisplay
        column={selectColumn()}
        row={{ ...row, cells: { status: 'sent' } }}
      />,
    );
    expect(screen.getByText('Sent')).toBeTruthy();
  });

  it('labels checkbox glyphs for screen readers', () => {
    render(
      <CellDisplay
        column={checkboxColumn()}
        row={{ ...row, cells: { contacted: true } }}
      />,
    );
    expect(screen.getByRole('img', { name: 'checked' })).toBeTruthy();
  });
});

describe('CellEditor', () => {
  it('text editor commits on Enter', () => {
    const onCommit = vi.fn();
    render(
      <CellEditor
        column={textColumn()}
        row={row}
        onCommit={onCommit}
        onCancel={vi.fn()}
      />,
    );
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Acme' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenCalledWith('Acme');
  });

  it('text editor cancels on Escape', () => {
    const onCancel = vi.fn();
    render(
      <CellEditor
        column={textColumn()}
        row={row}
        onCommit={vi.fn()}
        onCancel={onCancel}
      />,
    );
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('date editor commits null when left empty on blur', () => {
    const onCommit = vi.fn();
    render(
      <CellEditor
        column={{ key: 'date_sent', type: 'date', label: 'Date sent' }}
        row={row}
        onCommit={onCommit}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.blur(screen.getByLabelText('Date sent'));
    expect(onCommit).toHaveBeenCalledWith(null);
  });
});

function textColumn(): ColumnDefinition {
  return { key: 'company', type: 'text', label: 'Company' };
}

function selectColumn(): ColumnDefinition {
  return {
    key: 'status',
    type: 'select',
    label: 'Status',
    options: [
      { key: 'to_apply', label: 'To apply' },
      { key: 'sent', label: 'Sent' },
    ],
  };
}

function checkboxColumn(): ColumnDefinition {
  return { key: 'contacted', type: 'checkbox', label: 'Contacted' };
}
