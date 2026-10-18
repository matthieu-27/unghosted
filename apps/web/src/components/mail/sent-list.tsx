/** Sent-mail list (us-5 item 6): the read-back record of what went out. */

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { SentMessage } from '@/lib/mail-types';

interface SentListProps {
  messages: SentMessage[];
}

export function SentList({ messages }: SentListProps) {
  if (messages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing sent yet. A sent email appears here and updates its row.
      </p>
    );
  }
  return (
    <Table className="text-sm">
      <TableHeader>
        <TableRow>
          <TableHead scope="col" className="border-b px-2 text-left">
            Sent at
          </TableHead>
          <TableHead scope="col" className="border-b px-2 text-left">
            Recipient
          </TableHead>
          <TableHead scope="col" className="border-b px-2 text-left">
            Subject
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {messages.map((message) => (
          <TableRow key={message.id}>
            <TableCell className="px-2">
              {new Date(message.sent_at).toLocaleString()}
            </TableCell>
            <TableCell className="px-2">{message.recipient}</TableCell>
            <TableCell className="px-2">{message.subject}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
