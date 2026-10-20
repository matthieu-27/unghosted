import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Contact } from '@/lib/contact-types';
import { ContactForm } from './contact-form';

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
  notes: 'Met at a meetup',
  linked_row_count: 2,
  created_at: '2026-09-24T10:00:00+00:00',
  updated_at: '2026-09-24T10:00:00+00:00',
};

describe('ContactForm', () => {
  it('submits the typed fields for a new contact', async () => {
    const onSubmit = vi.fn();
    render(
      <ContactForm
        contact={null}
        saving={false}
        error={null}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fill('Name', 'Alice Martin');
    fill('Email', 'alice@dojoclub.example');
    fireEvent.click(screen.getByRole('button', { name: 'Add contact' }));

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Alice Martin',
      role: null,
      organization: null,
      email: 'alice@dojoclub.example',
      phone: null,
      profile_url: null,
      notes: null,
    });
  });

  it('fills the fields of an existing contact', () => {
    render(
      <ContactForm
        contact={CONTACT}
        saving={false}
        error={null}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe(
      'Martin Dupont',
    );
    expect(
      (screen.getByLabelText('Organization') as HTMLInputElement).value,
    ).toBe('Le Dojo Club');
    expect((screen.getByLabelText('Notes') as HTMLInputElement).value).toBe(
      'Met at a meetup',
    );
    expect(screen.getByRole('button', { name: 'Save contact' })).toBeTruthy();
  });

  it('sends null for a field the user emptied', async () => {
    const onSubmit = vi.fn();
    render(
      <ContactForm
        contact={CONTACT}
        saving={false}
        error={null}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    fill('Organization', '');
    fireEvent.click(screen.getByRole('button', { name: 'Save contact' }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ organization: null }),
    );
  });

  it('shows the server error above the fields', () => {
    render(
      <ContactForm
        contact={null}
        saving={false}
        error="Check the contact fields: a name is required."
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByRole('alert').textContent).toContain(
      'a name is required',
    );
  });

  it('disables the submit button while saving', () => {
    render(
      <ContactForm
        contact={null}
        saving={true}
        error={null}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(
      (screen.getByRole('button', { name: 'Add contact' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });
});
