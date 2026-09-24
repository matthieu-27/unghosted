/** Draft editor (us-5 items 2–5): edit the text, see the server-recomputed
 * grounding warnings, pick attachments, then approve (letter) or send
 * (first contact). The parent remounts this component with a fresh key
 * after every server write, so the local state never desyncs. */

import { useState } from 'react';

import { AttachmentsPicker } from '@/components/mail/attachments-picker';
import { Button } from '@/components/ui/button';
import type { DraftUpdateBody, MailDraft } from '@/lib/mail-types';
import type { DocumentSummary } from '@/lib/tracker-types';

interface DraftEditorProps {
  draft: MailDraft;
  documents: DocumentSummary[];
  saving: boolean;
  approving: boolean;
  sending: boolean;
  discarding: boolean;
  error: string | null;
  onSave: (body: DraftUpdateBody) => void;
  onApprove: () => void;
  onSend: () => void;
  onDiscard: () => void;
}

const KIND_LABELS: Record<string, string> = {
  customised_letter: 'Customised letter',
  first_contact_email: 'First-contact email',
};

export function DraftEditor({
  draft,
  documents,
  saving,
  approving,
  sending,
  discarding,
  error,
  onSave,
  onApprove,
  onSend,
  onDiscard,
}: DraftEditorProps) {
  const [text, setText] = useState(draft.text ?? '');
  const [subject, setSubject] = useState(draft.subject ?? '');
  const [recipient, setRecipient] = useState(draft.recipient ?? '');
  const [contactName, setContactName] = useState(draft.contact_name ?? '');
  const [attachments, setAttachments] = useState(draft.attachment_document_ids);

  const editable = draft.status === 'draft';
  const isLetter = draft.kind === 'customised_letter';

  /** PATCH body from the changed fields only: absent fields keep their
   * stored value server-side. */
  function buildUpdateBody(): DraftUpdateBody {
    const body: DraftUpdateBody = {};
    if (text !== (draft.text ?? '')) body.text = text;
    if (subject !== (draft.subject ?? '')) body.subject = subject;
    if (recipient !== (draft.recipient ?? '')) body.recipient = recipient;
    if (contactName !== (draft.contact_name ?? '')) {
      body.contact_name = contactName;
    }
    if (attachments.join(',') !== draft.attachment_document_ids.join(',')) {
      body.attachment_document_ids = attachments;
    }
    return body;
  }

  return (
    <section className="space-y-3 rounded-md border p-4">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-medium">
          {KIND_LABELS[draft.kind] ?? draft.kind} — {draft.status}
        </h2>
        <Button
          variant="outline"
          size="sm"
          disabled={discarding}
          onClick={onDiscard}
        >
          Discard
        </Button>
      </header>

      {draft.warnings.length > 0 ? (
        <ul className="space-y-1 rounded-md border border-amber-500 bg-amber-50 p-2 text-sm text-amber-900 dark:text-amber-200">
          {draft.warnings.map((warning) => (
            <li key={warning.code}>{warning.message}</li>
          ))}
        </ul>
      ) : null}

      <div className="grid gap-2 sm:grid-cols-3">
        <label className="text-sm">
          Recipient
          <input
            className="w-full rounded-md border px-2 py-1"
            value={recipient}
            disabled={!editable || isLetter}
            onChange={(event) => setRecipient(event.target.value)}
            placeholder="contact@company.example"
          />
        </label>
        <label className="text-sm">
          Contact name
          <input
            className="w-full rounded-md border px-2 py-1"
            value={contactName}
            disabled={!editable}
            onChange={(event) => setContactName(event.target.value)}
            placeholder="Martin"
          />
        </label>
        <label className="text-sm">
          Subject
          <input
            className="w-full rounded-md border px-2 py-1"
            value={subject}
            disabled={!editable || isLetter}
            onChange={(event) => setSubject(event.target.value)}
            placeholder="Candidature — alternance"
          />
        </label>
      </div>

      <label className="block text-sm">
        Text
        <textarea
          className="min-h-48 w-full rounded-md border px-2 py-1"
          value={text}
          disabled={!editable}
          onChange={(event) => setText(event.target.value)}
        />
      </label>

      {!isLetter ? (
        <AttachmentsPicker
          documents={documents}
          selectedIds={attachments}
          onChange={setAttachments}
        />
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!editable || saving}
          onClick={() => onSave(buildUpdateBody())}
        >
          Save
        </Button>
        {isLetter ? (
          <Button
            size="sm"
            disabled={!editable || approving}
            onClick={onApprove}
          >
            Approve letter as PDF
          </Button>
        ) : (
          <Button size="sm" disabled={!editable || sending} onClick={onSend}>
            Send
          </Button>
        )}
      </div>
    </section>
  );
}
