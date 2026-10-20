import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ContactDetail } from '@/lib/contact-types';
import { ContactDetailPanel } from './contact-detail';

afterEach(cleanup);

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

const DETAIL: ContactDetail = {
  contact: {
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
  },
  linked_row_ids: ['row-1'],
  threads: [
    {
      id: 't1',
      recipient: 'martin@dojoclub.example',
      message_count: 2,
      last_message_at: '2026-09-20T09:00:00+00:00',
    },
  ],
};

describe('ContactDetailPanel', () => {
  it('lists the linked rows and the mail threads', () => {
    render(
      <ContactDetailPanel
        detail={DETAIL}
        saving={false}
        error={null}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('row-1')).toBeTruthy();
    expect(
      screen.getByText(
        /martin@dojoclub.example — 2 messages, last on 2026-09-20/,
      ),
    ).toBeTruthy();
  });

  it('says so when the contact has no link and no thread', () => {
    render(
      <ContactDetailPanel
        detail={{ ...DETAIL, linked_row_ids: [], threads: [] }}
        saving={false}
        error={null}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/No row links this contact yet/)).toBeTruthy();
    expect(screen.getByText(/No email went to this contact yet/)).toBeTruthy();
  });

  it('saves the edited fields', async () => {
    const onSave = vi.fn();
    render(
      <ContactDetailPanel
        detail={DETAIL}
        saving={false}
        error={null}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    fill('Phone', '0601020304');
    fireEvent.click(screen.getByRole('button', { name: 'Save contact' }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ phone: '0601020304' }),
    );
  });

  it('closes the panel', async () => {
    const onClose = vi.fn();
    render(
      <ContactDetailPanel
        detail={DETAIL}
        saving={false}
        error={null}
        onSave={vi.fn()}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalled();
  });
});
