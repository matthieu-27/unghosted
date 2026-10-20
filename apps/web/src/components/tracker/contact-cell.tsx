/**
 * The contact-link cell (us-7 item 2): a row links one or more of the
 * project's contacts. The cell holds contact ids, so the display resolves
 * them against the project's contact list and the editor picks from it.
 */

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import type { Contact } from '@/lib/contact-types';

export function contactIds(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v) => typeof v === 'string') : [];
}

export function ContactCellDisplay({
  value,
  contacts,
}: {
  value: unknown;
  contacts: Contact[];
}) {
  const ids = contactIds(value);
  if (ids.length === 0) return <span className="text-muted-foreground">—</span>;
  const names = new Map(contacts.map((contact) => [contact.id, contact.name]));
  return (
    <span>
      {ids.map((id, index) => (
        <span key={id}>
          {index > 0 ? ', ' : ''}
          {names.has(id) ? (
            <span>{names.get(id)}</span>
          ) : (
            <span
              className="text-destructive"
              title="No contact in this project carries this id"
            >
              {id}
            </span>
          )}
        </span>
      ))}
    </span>
  );
}

interface ContactCellEditorProps {
  label: string;
  value: unknown;
  contacts: Contact[];
  onCommit: (value: string[]) => void;
  onCancel: () => void;
}

export function ContactCellEditor({
  label,
  value,
  contacts,
  onCommit,
  onCancel,
}: ContactCellEditorProps) {
  const selected = new Set(contactIds(value));

  if (contacts.length === 0) {
    return (
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">
          No contact in this project yet.
        </p>
        <Button variant="outline" size="sm" onClick={onCancel}>
          Close
        </Button>
      </div>
    );
  }

  return (
    <fieldset
      className="space-y-1 rounded-md border bg-background p-2"
      onKeyDown={(event) => {
        if (event.key === 'Escape') onCancel();
      }}
    >
      <legend className="text-xs font-medium">{label}</legend>
      {contacts.map((contact) => {
        const inputId = `contact-${contact.id}`;
        return (
          <div key={contact.id} className="flex items-center gap-2">
            <Checkbox
              id={inputId}
              checked={selected.has(contact.id)}
              onCheckedChange={(checked) => {
                const next = new Set(selected);
                if (checked) next.add(contact.id);
                else next.delete(contact.id);
                // Committing on every toggle keeps one write path: the cell
                // is the source of truth, the server re-indexes the links.
                onCommit(
                  contacts
                    .map((candidate) => candidate.id)
                    .filter((id) => next.has(id)),
                );
              }}
            />
            <Label htmlFor={inputId} className="text-xs">
              {contact.name}
            </Label>
          </div>
        );
      })}
      <Button variant="outline" size="sm" onClick={onCancel}>
        Done
      </Button>
    </fieldset>
  );
}
