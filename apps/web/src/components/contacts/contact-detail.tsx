/**
 * Detail panel for one contact (us-7 item 1): the editable fields, the
 * tracker rows it is linked to, and the mail threads addressed to it.
 */

import { ContactForm } from '@/components/contacts/contact-form';
import { Button } from '@/components/ui/button';
import type { ContactDetail, ContactInput } from '@/lib/contact-types';

interface ContactDetailPanelProps {
  detail: ContactDetail;
  saving: boolean;
  error: string | null;
  onSave: (input: ContactInput) => void;
  onClose: () => void;
}

function threadLabel(messageCount: number): string {
  return messageCount === 1 ? '1 message' : `${messageCount} messages`;
}

export function ContactDetailPanel({
  detail,
  saving,
  error,
  onSave,
  onClose,
}: ContactDetailPanelProps) {
  const { contact, linked_row_ids: linkedRowIds, threads } = detail;
  return (
    <section
      aria-label={`Contact ${contact.name}`}
      className="space-y-4 rounded-md border p-4"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">{contact.name}</h2>
        <Button variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      <ContactForm
        contact={contact}
        saving={saving}
        error={error}
        onSubmit={onSave}
      />

      <div className="space-y-1">
        <h3 className="text-xs font-medium">Linked tracker rows</h3>
        {linkedRowIds.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No row links this contact yet.
          </p>
        ) : (
          <ul className="text-xs text-muted-foreground">
            {linkedRowIds.map((rowId) => (
              <li key={rowId}>{rowId}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-1">
        <h3 className="text-xs font-medium">Mail threads</h3>
        {threads.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No email went to this contact yet.
          </p>
        ) : (
          <ul className="text-xs text-muted-foreground">
            {threads.map((thread) => (
              <li key={thread.id}>
                {thread.recipient} — {threadLabel(thread.message_count)}
                {thread.last_message_at
                  ? `, last on ${thread.last_message_at.slice(0, 10)}`
                  : ''}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
