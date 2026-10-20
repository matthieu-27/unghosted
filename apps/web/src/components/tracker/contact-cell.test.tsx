import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Contact } from '@/lib/contact-types';
import { ContactCellDisplay, ContactCellEditor } from './contact-cell';

afterEach(cleanup);

/** Base UI's Checkbox pairs aria-label with the visible label, so the
 * accessible name repeats the contact name: match it loosely. */
function checkbox(name: string) {
  return screen.getByRole('checkbox', { name: new RegExp(name) });
}

function contact(id: string, name: string): Contact {
  return {
    id,
    name,
    role: null,
    organization: null,
    email: null,
    phone: null,
    profile_url: null,
    notes: null,
    linked_row_count: 0,
    created_at: '2026-09-24T10:00:00+00:00',
    updated_at: '2026-09-24T10:00:00+00:00',
  };
}

const CONTACTS = [
  contact('c1', 'Martin Dupont'),
  contact('c2', 'Alice Martin'),
];

describe('ContactCellDisplay', () => {
  it('shows the names behind the linked ids', () => {
    render(<ContactCellDisplay value={['c1', 'c2']} contacts={CONTACTS} />);
    expect(screen.getByText('Martin Dupont')).toBeTruthy();
    expect(screen.getByText('Alice Martin')).toBeTruthy();
  });

  it('shows a dash for an empty cell', () => {
    render(<ContactCellDisplay value={null} contacts={CONTACTS} />);
    expect(screen.getByText('—')).toBeTruthy();
  });

  it('marks an id no contact matches as unknown', () => {
    render(<ContactCellDisplay value={['ghost']} contacts={CONTACTS} />);
    // An unresolved id shows itself, not a blanket "Unknown": the orphan
    // stays visible and identifiable (fallow tradeoff 3).
    expect(screen.getByText('ghost')).toBeTruthy();
    expect(screen.queryByText('Unknown')).toBeNull();
  });

  it('names the contacts it can resolve around one it cannot', () => {
    render(
      <ContactCellDisplay value={['c1', 'ghost', 'c2']} contacts={CONTACTS} />,
    );
    expect(screen.getByText('Martin Dupont')).toBeTruthy();
    expect(screen.getByText('Alice Martin')).toBeTruthy();
    expect(screen.getByText('ghost')).toBeTruthy();
  });
});

describe('ContactCellEditor', () => {
  it('adds a contact to the cell when its box is checked', async () => {
    const onCommit = vi.fn();
    render(
      <ContactCellEditor
        label="Contact"
        value={['c1']}
        contacts={CONTACTS}
        onCommit={onCommit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(checkbox('Alice Martin'));
    expect(onCommit).toHaveBeenCalledWith(['c1', 'c2']);
  });

  it('removes a contact when its box is unchecked', async () => {
    const onCommit = vi.fn();
    render(
      <ContactCellEditor
        label="Contact"
        value={['c1', 'c2']}
        contacts={CONTACTS}
        onCommit={onCommit}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(checkbox('Martin Dupont'));
    expect(onCommit).toHaveBeenCalledWith(['c2']);
  });

  it('tells the user when the project has no contact yet', () => {
    render(
      <ContactCellEditor
        label="Contact"
        value={null}
        contacts={[]}
        onCommit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText(/No contact in this project yet/)).toBeTruthy();
  });

  it('closes on Escape', async () => {
    const onCancel = vi.fn();
    render(
      <ContactCellEditor
        label="Contact"
        value={null}
        contacts={CONTACTS}
        onCommit={vi.fn()}
        onCancel={onCancel}
      />,
    );

    fireEvent.click(checkbox('Martin Dupont'));
    fireEvent.keyDown(screen.getByRole('group'), { key: 'Escape' });
    expect(onCancel).toHaveBeenCalled();
  });
});
