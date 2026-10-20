/**
 * Create/edit form for one contact (us-7 item 1). The same form serves both:
 * an existing contact fills the fields, a new one starts empty.
 */

import { useId } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { Contact, ContactInput } from '@/lib/contact-types';

const TEXT_FIELDS = [
  { key: 'name', label: 'Name', type: 'text', required: true },
  { key: 'role', label: 'Role', type: 'text', required: false },
  { key: 'organization', label: 'Organization', type: 'text', required: false },
  { key: 'email', label: 'Email', type: 'email', required: false },
  { key: 'phone', label: 'Phone', type: 'tel', required: false },
  { key: 'profile_url', label: 'Profile URL', type: 'url', required: false },
] as const;

type TextFieldKey = (typeof TEXT_FIELDS)[number]['key'];

interface ContactFormProps {
  contact: Contact | null;
  saving: boolean;
  error: string | null;
  onSubmit: (input: ContactInput) => void;
  onCancel?: () => void;
}

/** Empty inputs are sent as null: "cleared" is a value the API understands,
 * "" is not. */
function valueOrNull(form: FormData, key: string): string | null {
  const value = form.get(key);
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

export function ContactForm({
  contact,
  saving,
  error,
  onSubmit,
  onCancel,
}: ContactFormProps) {
  const formId = useId();
  const fieldId = (key: string) => `${formId}-${key}`;

  return (
    <form
      aria-label={contact ? 'Edit contact' : 'New contact'}
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        onSubmit({
          name: (form.get('name') as string).trim(),
          role: valueOrNull(form, 'role'),
          organization: valueOrNull(form, 'organization'),
          email: valueOrNull(form, 'email'),
          phone: valueOrNull(form, 'phone'),
          profile_url: valueOrNull(form, 'profile_url'),
          notes: valueOrNull(form, 'notes'),
        });
      }}
    >
      {error ? (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {TEXT_FIELDS.map((field) => (
          <div key={field.key} className="space-y-1">
            <Label htmlFor={fieldId(field.key)}>{field.label}</Label>
            <Input
              id={fieldId(field.key)}
              name={field.key}
              type={field.type}
              required={field.required}
              defaultValue={fieldValue(contact, field.key)}
            />
          </div>
        ))}
      </div>
      <div className="space-y-1">
        <Label htmlFor={fieldId('notes')}>Notes</Label>
        <Textarea
          id={fieldId('notes')}
          name="notes"
          rows={3}
          defaultValue={contact?.notes ?? ''}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={saving}>
          {contact ? 'Save contact' : 'Add contact'}
        </Button>
        {onCancel ? (
          <Button type="button" variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function fieldValue(contact: Contact | null, key: TextFieldKey): string {
  return contact?.[key] ?? '';
}
