/** Mail workspace: draft, edit, approve, send for one tracker row. */

import { createFileRoute } from '@tanstack/react-router';

import { MailPage } from '@/components/mail/mail-page';

/** Flow state lives in the URL (ADR 0003): ?row=… selects the tracker
 * row, ?draft=… the draft being edited. */
interface MailSearch {
  row: string | undefined;
  draft: string | undefined;
}

export const Route = createFileRoute('/_authed/projects/$projectId/mail')({
  validateSearch: (search: Record<string, unknown>): MailSearch => ({
    row: typeof search.row === 'string' ? search.row : undefined,
    draft: typeof search.draft === 'string' ? search.draft : undefined,
  }),
  component: MailRoute,
});

function MailRoute() {
  const { projectId } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  if (search.row === undefined) {
    return (
      <main className="container mx-auto p-8">
        <p className="text-sm text-muted-foreground">
          Open a row in the tracker and pick “Write first contact”.
        </p>
      </main>
    );
  }

  return (
    <MailPage
      projectId={projectId}
      rowId={search.row}
      draftId={search.draft ?? null}
      onOpenDraft={(draftId) => {
        void navigate({ search: { row: search.row, draft: draftId } });
      }}
      onClearDraft={() => {
        void navigate({ search: { row: search.row, draft: undefined } });
      }}
    />
  );
}
