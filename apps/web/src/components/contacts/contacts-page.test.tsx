import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  detail: { data: undefined as unknown },
  contacts: { data: [] as unknown[], isError: false },
}));

const FakeApiError = vi.hoisted(
  () =>
    class FakeApiError extends Error {
      constructor(
        readonly code: string,
        message: string,
      ) {
        super(message);
      }
    },
);

vi.mock('@/lib/api', () => ({
  ApiError: FakeApiError,
  apiFetch: h.apiFetch,
}));

function mutation(mutate: ReturnType<typeof vi.fn>, error: unknown = null) {
  return { mutate, isPending: false, error };
}

vi.mock('@/hooks/use-contacts', () => ({
  useContacts: () => h.contacts,
  useContact: () => h.detail,
  useCreateContact: () => mutation(h.create),
  useUpdateContact: () => mutation(h.update),
  useDeleteContact: () => mutation(h.remove),
}));

import { ContactsPage, contactActionMessage } from './contacts-page';

const CONTACT = {
  id: 'c1',
  name: 'Martin Dupont',
  role: 'Head of data',
  organization: 'Le Dojo Club',
  email: 'martin@dojoclub.example',
  phone: null,
  profile_url: null,
  notes: null,
  linked_row_count: 1,
  created_at: '2026-09-24T10:00:00+00:00',
  updated_at: '2026-09-24T10:00:00+00:00',
};

function renderPage(selectedContactId: string | null = null) {
  const onSelectContact = vi.fn();
  const onClearContact = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <ContactsPage
        projectId="p1"
        selectedContactId={selectedContactId}
        onSelectContact={onSelectContact}
        onClearContact={onClearContact}
      />
    </QueryClientProvider>,
  );
  return { onSelectContact, onClearContact };
}

beforeEach(() => {
  h.apiFetch.mockReset().mockResolvedValue({ name: 'Search' });
  h.create.mockReset();
  h.update.mockReset();
  h.remove.mockReset();
  h.contacts = { data: [CONTACT], isError: false };
  h.detail = { data: undefined };
});

afterEach(cleanup);

describe('ContactsPage', () => {
  it('lists the project contacts', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Martin Dupont')).toBeTruthy());
  });

  it('opens the new-contact form and creates a contact', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '+ New contact' }));
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Alice Martin' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add contact' }));

    await waitFor(() => expect(h.create).toHaveBeenCalled());
    expect(h.create.mock.calls[0]?.[0]).toMatchObject({ name: 'Alice Martin' });
  });

  it('asks the router to open the contact the user picked', async () => {
    const { onSelectContact } = renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    await waitFor(() => expect(onSelectContact).toHaveBeenCalledWith('c1'));
  });

  it('deletes a contact from the list', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(h.remove.mock.calls[0]?.[0]).toBe('c1'));
  });

  it('shows the detail panel of the selected contact', async () => {
    h.detail = {
      data: { contact: CONTACT, linked_row_ids: ['row-1'], threads: [] },
    };
    renderPage('c1');
    await waitFor(() => expect(screen.getByText('row-1')).toBeTruthy());
  });

  it('reports a failing contact list', async () => {
    h.contacts = { data: [], isError: true };
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toContain(
        'Cannot load contacts',
      ),
    );
  });
});

describe('contactActionMessage', () => {
  it('turns a known error code into a sentence', () => {
    expect(
      contactActionMessage(new FakeApiError('validation_failed', 'raw')),
    ).toBe('Check the contact fields: a name is required.');
  });

  it('keeps the server message for an unknown code', () => {
    expect(contactActionMessage(new FakeApiError('teapot', 'raw'))).toBe('raw');
  });

  it('returns null for a non-error value', () => {
    expect(contactActionMessage('nope')).toBeNull();
  });
});
