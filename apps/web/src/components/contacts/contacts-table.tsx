/** Contact list with the search box (us-7 item 1). */

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { Contact } from '@/lib/contact-types';

interface ContactsTableProps {
  contacts: Contact[];
  search: string;
  selectedId: string | undefined;
  deleting: boolean;
  error: string | null;
  onSearchChange: (search: string) => void;
  onSelect: (contact: Contact) => void;
  onDelete: (contact: Contact) => void;
}

export function ContactsTable({
  contacts,
  search,
  selectedId,
  deleting,
  error,
  onSearchChange,
  onSelect,
  onDelete,
}: ContactsTableProps) {
  return (
    <section aria-label="Contacts" className="space-y-2">
      <div className="max-w-xs space-y-1">
        <Label htmlFor="contact-search">Search contacts</Label>
        <Input
          id="contact-search"
          type="search"
          value={search}
          placeholder="Name, organization, role or email"
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </div>
      {error ? (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      ) : null}
      {contacts.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No contact matches. Add one to start.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Organization</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Linked rows</TableHead>
              <TableHead aria-label="Actions" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((contact) => (
              <TableRow
                key={contact.id}
                data-selected={contact.id === selectedId}
                className="data-[selected=true]:bg-muted"
              >
                <TableCell>{contact.name}</TableCell>
                <TableCell>{contact.role ?? '—'}</TableCell>
                <TableCell>{contact.organization ?? '—'}</TableCell>
                <TableCell>{contact.email ?? '—'}</TableCell>
                <TableCell>{contact.linked_row_count}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onSelect(contact)}
                    >
                      Open
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={deleting}
                      onClick={() => onDelete(contact)}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
