/**
 * Contacts page body (us-7): search, list, create, detail panel with edit
 * and delete. The route file keeps the router wiring and the URL state.
 */

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { ContactDetailPanel } from '@/components/contacts/contact-detail';
import { ContactForm } from '@/components/contacts/contact-form';
import { ContactsTable } from '@/components/contacts/contacts-table';
import { Button } from '@/components/ui/button';
import {
  useContact,
  useContacts,
  useCreateContact,
  useDeleteContact,
  useUpdateContact,
} from '@/hooks/use-contacts';
import { ApiError, apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { ProjectSummary } from '@/lib/tracker-types';

const CONTACT_ERROR_MESSAGES: Record<string, string> = {
  validation_failed: 'Check the contact fields: a name is required.',
  not_found: 'This contact no longer exists.',
};

/** Maps an API error code to the user-facing sentence; other errors keep
 * the server detail. */
export function contactActionMessage(error: unknown): string | null {
  if (error instanceof ApiError) {
    return CONTACT_ERROR_MESSAGES[error.code ?? ''] ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return null;
}

interface ContactsPageProps {
  projectId: string;
  selectedContactId: string | null;
  onSelectContact: (contactId: string) => void;
  onClearContact: () => void;
}

export function ContactsPage({
  projectId,
  selectedContactId,
  onSelectContact,
  onClearContact,
}: ContactsPageProps) {
  const [search, setSearch] = useState('');
  const [adding, setAdding] = useState(false);

  const project = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => apiFetch<ProjectSummary>(`/projects/${projectId}`),
  });
  const contacts = useContacts(projectId, search);
  const detail = useContact(projectId, selectedContactId ?? undefined);
  const create = useCreateContact(projectId);
  const update = useUpdateContact(projectId);
  const remove = useDeleteContact(projectId);

  if (contacts.isError) {
    return (
      <main className="container mx-auto p-8">
        <p role="alert" className="text-sm text-red-600">
          Cannot load contacts.
        </p>
      </main>
    );
  }

  return (
    <main className="container mx-auto space-y-6 p-8">
      <h1 className="text-lg font-medium">
        Contacts — {project.data?.name ?? '…'}
      </h1>

      {adding ? (
        <ContactForm
          contact={null}
          saving={create.isPending}
          error={contactActionMessage(create.error)}
          onSubmit={(input) => {
            create.mutate(input, { onSuccess: () => setAdding(false) });
          }}
          onCancel={() => setAdding(false)}
        />
      ) : (
        <Button size="sm" onClick={() => setAdding(true)}>
          + New contact
        </Button>
      )}

      <ContactsTable
        contacts={contacts.data ?? []}
        search={search}
        selectedId={selectedContactId ?? undefined}
        deleting={remove.isPending}
        error={contactActionMessage(remove.error)}
        onSearchChange={setSearch}
        onSelect={(contact) => onSelectContact(contact.id)}
        onDelete={(contact) => {
          remove.mutate(contact.id, {
            onSuccess: () => {
              if (contact.id === selectedContactId) onClearContact();
            },
          });
        }}
      />

      {detail.data ? (
        <ContactDetailPanel
          detail={detail.data}
          saving={update.isPending}
          error={contactActionMessage(update.error)}
          onSave={(changes) => {
            update.mutate({ contactId: detail.data.contact.id, changes });
          }}
          onClose={onClearContact}
        />
      ) : null}
    </main>
  );
}
