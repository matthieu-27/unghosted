/**
 * Mail page body (us-5): draft a customised letter or a first-contact
 * email for one tracker row, edit, attach, send, read the sent list. The
 * route file keeps the router wiring and passes the URL state.
 */

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { DraftEditor } from '@/components/mail/draft-editor';
import { SentList } from '@/components/mail/sent-list';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useDocuments } from '@/hooks/use-documents';
import {
  useApproveLetterDraft,
  useDiscardDraft,
  useDraftFirstContact,
  useDraftLetter,
  useMailDraft,
  useSendDraft,
  useSentMessages,
  useUpdateDraft,
} from '@/hooks/use-mail';
import { useTracker } from '@/hooks/use-tracker';
import { ApiError, apiFetch } from '@/lib/api';
import type { DraftUpdateBody } from '@/lib/mail-types';
import { queryKeys } from '@/lib/query-keys';
import type { ProjectSummary } from '@/lib/tracker-types';

const MAIL_ERROR_MESSAGES: Record<string, string> = {
  consent_required: 'Grant model-processing consent first (documents page).',
  no_approved_profile: 'Approve an applicant profile first (documents page).',
  no_listing_text:
    'This row has no analyzed listing. Run the listing analysis first.',
  model_unavailable: 'The model provider is unavailable. Try again later.',
  draft_state: 'This draft is closed. Draft a new one.',
  send_validation: 'Set a recipient, a subject and a body before sending.',
  daily_cap_reached: 'Daily send cap reached for this project.',
  recipient_cooldown: 'An email went to this recipient less than 7 days ago.',
  mail_send_failed: 'Delivery failed. Nothing was sent. Try again later.',
  row_update_failed:
    'The email was sent but the row could not be updated. Refresh the tracker and set the date manually.',
  pdf_render_failed: 'Letter rendering failed. Try again later.',
  document_type_invalid: 'This project cannot store generated letters.',
};

/** Maps an API error code to the user-facing sentence; other errors keep
 * the server detail. */
export function mailActionMessage(error: unknown): string | null {
  if (error instanceof ApiError) {
    return MAIL_ERROR_MESSAGES[error.code ?? ''] ?? error.message;
  }
  if (error instanceof Error) return error.message;
  return null;
}

function firstErrorMessage(errors: unknown[]): string | null {
  for (const error of errors) {
    if (error) return mailActionMessage(error);
  }
  return null;
}

function rowCompany(
  rows: { id: string; cells: Record<string, unknown> }[] | undefined,
  rowId: string,
): string {
  const row = rows?.find((candidate) => candidate.id === rowId);
  const company = row?.cells.company;
  return typeof company === 'string' ? company : '…';
}

interface MailPageProps {
  projectId: string;
  rowId: string;
  draftId: string | null;
  onOpenDraft: (draftId: string) => void;
  onClearDraft: () => void;
}

export function MailPage({
  projectId,
  rowId,
  draftId,
  onOpenDraft,
  onClearDraft,
}: MailPageProps) {
  const [recipient, setRecipient] = useState('');

  const project = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => apiFetch<ProjectSummary>(`/projects/${projectId}`),
  });
  const tracker = useTracker(projectId);
  const documents = useDocuments(projectId);
  const draft = useMailDraft(projectId, draftId);
  const sent = useSentMessages(projectId);

  const draftLetter = useDraftLetter(projectId);
  const draftFirstContact = useDraftFirstContact(projectId);
  const update = useUpdateDraft(projectId);
  const approve = useApproveLetterDraft(projectId);
  const discard = useDiscardDraft(projectId);
  const send = useSendDraft(projectId);

  if (project.isError) {
    return (
      <main className="container mx-auto p-8">
        <p role="alert" className="text-sm text-red-600">
          Cannot load project.
        </p>
      </main>
    );
  }

  const mutationError = firstErrorMessage([
    draftLetter.error,
    draftFirstContact.error,
    update.error,
    approve.error,
    discard.error,
    send.error,
  ]);

  function openDraft(result: { id: string }) {
    onOpenDraft(result.id);
  }

  function saveDraft(body: DraftUpdateBody) {
    if (draftId === null) return;
    update.mutate({ draftId, body });
  }

  function approveLetter() {
    if (draftId === null) return;
    approve.mutate(draftId, {
      onSuccess: () => onClearDraft(),
    });
  }

  function sendEmail() {
    if (draftId === null) return;
    send.mutate({ draftId, body: {} });
  }

  function discardDraft() {
    if (draftId === null) return;
    discard.mutate(draftId, {
      onSuccess: () => onClearDraft(),
    });
  }

  return (
    <main className="container mx-auto space-y-6 p-8">
      <h1 className="text-lg font-medium">
        Mail — {rowCompany(tracker.data?.rows, rowId)} (
        {project.data?.name ?? '…'})
      </h1>

      {draftId === null ? (
        <section className="space-y-2 rounded-md border p-4">
          <h2 className="text-sm font-medium">Start a draft for this row</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              disabled={draftLetter.isPending}
              onClick={() =>
                draftLetter.mutate(
                  { rowId, body: {} },
                  { onSuccess: openDraft },
                )
              }
            >
              Draft letter
            </Button>
            <Input
              type="email"
              className="w-64"
              aria-label="First-contact recipient"
              placeholder="contact@company.example"
              value={recipient}
              onChange={(event) => setRecipient(event.target.value)}
            />
            <Button
              size="sm"
              disabled={draftFirstContact.isPending || recipient === ''}
              onClick={() =>
                draftFirstContact.mutate(
                  { rowId, body: { recipient } },
                  { onSuccess: openDraft },
                )
              }
            >
              Draft first contact
            </Button>
          </div>
        </section>
      ) : draft.data ? (
        // Remount on every server write so the editor resets to the
        // server's view of the draft.
        <DraftEditor
          key={`${draft.data.id}:${draft.data.updated_at}`}
          draft={draft.data}
          documents={documents.data ?? []}
          saving={update.isPending}
          approving={approve.isPending}
          sending={send.isPending}
          discarding={discard.isPending}
          error={mutationError}
          onSave={saveDraft}
          onApprove={approveLetter}
          onSend={sendEmail}
          onDiscard={discardDraft}
        />
      ) : draft.isError ? (
        <p role="alert" className="text-sm text-red-600">
          Cannot load draft ({mailActionMessage(draft.error)}).
        </p>
      ) : (
        <p>Loading…</p>
      )}

      {mutationError && (draftId === null || !draft.data) ? (
        <p role="alert" className="text-sm text-red-600">
          {mutationError}
        </p>
      ) : null}

      <section className="space-y-2">
        <h2 className="text-sm font-medium">Sent</h2>
        {sent.data ? <SentList messages={sent.data} /> : <p>Loading…</p>}
      </section>
    </main>
  );
}
