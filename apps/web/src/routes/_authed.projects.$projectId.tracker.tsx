/** Tracker workspace: summary strip, cell bar, editable grid, autosave.
 * The project shell above owns the identity row and section nav. */

import { AlertCircleIcon, Table01Icon } from '@hugeicons/core-free-icons';
import { HugeiconsIcon } from '@hugeicons/react';
import { createFileRoute } from '@tanstack/react-router';

import { CellBar } from '@/components/tracker/cell-bar';
import { NewApplicationModal } from '@/components/tracker/new-application-modal';
import { TrackerGrid } from '@/components/tracker/tracker-grid';
import { TrackerSkeleton } from '@/components/tracker/tracker-skeleton';
import { TrackerSummary } from '@/components/tracker/tracker-summary';
import { Button } from '@/components/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty';
import { SaveStatusIndicator } from '@/components/workspace/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { useContacts } from '@/hooks/use-contacts';
import { useTracker } from '@/hooks/use-tracker';
import { distribution, fillRate } from '@/lib/tracker-stats';

/** Modal state lives in the URL (ADR 0003): ?new=1 opens the flow. */
interface TrackerSearch {
  new?: boolean;
}

export const Route = createFileRoute('/_authed/projects/$projectId/tracker')({
  validateSearch: (search: Record<string, unknown>): TrackerSearch => ({
    new: search.new === true ? true : undefined,
  }),
  component: TrackerPage,
});

/** Autosave against whatever the tracker query currently holds. */
function useTrackerAutosave(
  projectId: string,
  data: ReturnType<typeof useTracker>['data'],
) {
  return useAutosave(projectId, data?.rows, data?.definition.revision);
}

function TrackerPage() {
  const { projectId } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  const tracker = useTracker(projectId);
  // The whole unfiltered list: contact-link cells resolve ids against it
  // (us-7 item 2), so the grid needs every contact, not a search page.
  const contacts = useContacts(projectId);
  const { rows, status, push } = useTrackerAutosave(projectId, tracker.data);

  if (tracker.isError) {
    return (
      <div
        role="alert"
        className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
      >
        <HugeiconsIcon
          icon={AlertCircleIcon}
          strokeWidth={2}
          className="size-4"
        />
        Cannot load tracker ({String(tracker.error)}).
      </div>
    );
  }
  if (tracker.isPending || !tracker.data) {
    return <TrackerSkeleton />;
  }

  const columns = tracker.data.definition.columns;
  const summary = distribution(columns, rows);
  const fill = fillRate(columns, rows);
  const empty = rows.length === 0;

  return (
    <div className="flex flex-col gap-4">
      {empty ? (
        <Empty className="animate-in fade-in slide-in-from-bottom-2 rounded-xl border bg-card duration-300">
          <EmptyMedia className="bg-muted">
            <HugeiconsIcon
              icon={Table01Icon}
              strokeWidth={2}
              className="size-5"
            />
          </EmptyMedia>
          <EmptyTitle>Empty tracker</EmptyTitle>
          <EmptyDescription>
            Track each application as a row — company, link, status, dates. Or
            start from a listing with the guided flow.
          </EmptyDescription>
          <EmptyContent className="flex gap-2">
            <Button onClick={() => push({ op: 'insert_rows', count: 1 })}>
              Add a row
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                void navigate({ search: { new: true } });
              }}
            >
              + New application
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <>
          <TrackerSummary
            rowCount={rows.length}
            distribution={summary}
            fill={fill}
          />
          <div className="flex animate-in fade-in delay-75 flex-wrap items-center gap-2 duration-300">
            <CellBar
              column={columns[0]}
              columnIndex={0}
              row={rows[0]}
              rowIndex={0}
            />
            <SaveStatusIndicator status={status} />
            <div className="ms-auto">
              <Button
                aria-expanded={search.new === true}
                onClick={() => {
                  void navigate({ search: { new: true } });
                }}
              >
                + New application
              </Button>
            </div>
          </div>
          <div className="animate-in fade-in slide-in-from-bottom-2 delay-150 duration-300">
            <TrackerGrid
              columns={columns}
              rows={rows}
              contacts={contacts.data ?? []}
              onOperation={push}
              onAddRow={() => push({ op: 'insert_rows', count: 1 })}
              onDeleteRow={(rowId) =>
                push({ op: 'delete_rows', row_ids: [rowId] })
              }
              onWriteMail={(rowId) => {
                void navigate({
                  to: '/projects/$projectId/mail',
                  params: { projectId },
                  search: { row: rowId, draft: undefined },
                });
              }}
            />
          </div>
        </>
      )}
      <NewApplicationModal
        open={search.new === true}
        projectId={projectId}
        columns={columns}
        revision={tracker.data.definition.revision}
        onClose={() => {
          void navigate({ search: { new: undefined } });
        }}
      />
    </div>
  );
}
