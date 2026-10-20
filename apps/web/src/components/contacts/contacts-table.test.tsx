import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Contact } from '@/lib/contact-types';
import { ContactsTable } from './contacts-table';

afterEach(cleanup);

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

const CONTACT: Contact = {
  id: 'c1',
  name: 'Martin Dupont',
  role: 'Head of data',
  organization: 'Le Dojo Club',
  email: 'martin@dojoclub.example',
  phone: null,
  profile_url: null,
  notes: null,
  linked_row_count: 2,
  created_at: '2026-09-24T10:00:00+00:00',
  updated_at: '2026-09-24T10:00:00+00:00',
};

function renderTable(overrides: Partial<Parameters<typeof ContactsTable>[0]>) {
  const props = {
    contacts: [CONTACT],
    search: '',
    selectedId: undefined,
    deleting: false,
    error: null,
    onSearchChange: vi.fn(),
    onSelect: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  render(<ContactsTable {...props} />);
  return props;
}

describe('ContactsTable', () => {
  it('shows one row per contact with its linked-row count', () => {
    renderTable({});
    expect(screen.getByText('Martin Dupont')).toBeTruthy();
    expect(screen.getByText('Le Dojo Club')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
  });

  it('tells the user when nothing matches', () => {
    renderTable({ contacts: [] });
    expect(screen.getByText(/No contact matches/)).toBeTruthy();
  });

  it('reports what the user types in the search box', async () => {
    const props = renderTable({});
    fill('Search contacts', 'd');
    expect(props.onSearchChange).toHaveBeenCalledWith('d');
  });

  it('opens a contact when its Open button is pressed', async () => {
    const props = renderTable({});
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    expect(props.onSelect).toHaveBeenCalledWith(CONTACT);
  });

  it('deletes a contact when its Delete button is pressed', async () => {
    const props = renderTable({});
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(props.onDelete).toHaveBeenCalledWith(CONTACT);
  });

  it('disables deletion while a delete is in flight', () => {
    renderTable({ deleting: true });
    expect(
      (screen.getByRole('button', { name: 'Delete' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it('shows the delete error', () => {
    renderTable({ error: 'This contact no longer exists.' });
    expect(screen.getByRole('alert').textContent).toContain('no longer exists');
  });
});
