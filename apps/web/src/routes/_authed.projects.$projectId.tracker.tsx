/** Tracker workspace: title row, cell bar, editable grid, autosave. */

import { useQuery } from '@tanstack/react-query';
import { createFileRoute } from '@tanstack/react-router';

import { CellBar } from '@/components/tracker/cell-bar';
import { NewApplicationModal } from '@/components/tracker/new-application-modal';
import { TrackerGrid } from '@/components/tracker/tracker-grid';
import { Button } from '@/components/ui/button';
import { TitleRow } from '@/components/workspace/title-row';
import { useAutosave } from '@/hooks/use-autosave';
import { useTracker } from '@/hooks/use-tracker';
import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { ProjectSummary, TrackerPayload } from '@/lib/tracker-types';

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

function projectName(summary: ProjectSummary | undefined): string {
  return summary?.name ?? '…';
}

/** Autosave against whatever the tracker query currently holds. */
function useTrackerAutosave(
  projectId: string,
  data: TrackerPayload | undefined,
) {
  return useAutosave(projectId, data?.rows, data?.definition.revision);
}

function TrackerPage() {
  const { projectId } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  const project = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => apiFetch<ProjectSummary>(`/projects/${projectId}`),
  });
  const tracker = useTracker(projectId);
  const { rows, status, push } = useTrackerAutosave(projectId, tracker.data);

  if (tracker.isError) {
    return (
      <main className="container mx-auto p-8">
        <p role="alert" className="text-sm text-red-600">
          Cannot load tracker ({String(tracker.error)}).
        </p>
      </main>
    );
  }
  if (tracker.isPending || !tracker.data) {
    return (
      <main className="container mx-auto p-8">
        <p>Loading…</p>
      </main>
    );
  }

  const columns = tracker.data.definition.columns;

  return (
    <main className="flex min-h-svh flex-col">
      <TitleRow projectName={projectName(project.data)} saveStatus={status} />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <CellBar
          column={columns[0]}
          columnIndex={0}
          row={rows[0]}
          rowIndex={0}
        />
        <div>
          <Button
            variant="outline"
            size="sm"
            aria-expanded={search.new === true}
            onClick={() => {
              void navigate({ search: { new: true } });
            }}
          >
            + New application
          </Button>
        </div>
        <TrackerGrid
          columns={columns}
          rows={rows}
          onOperation={push}
          onAddRow={() => push({ op: 'insert_rows', count: 1 })}
          onDeleteRow={(rowId) => push({ op: 'delete_rows', row_ids: [rowId] })}
          onWriteMail={(rowId) => {
            void navigate({
              to: '/projects/$projectId/mail',
              params: { projectId },
              search: { row: rowId, draft: undefined },
            });
          }}
        />
      </div>
      <NewApplicationModal
        open={search.new === true}
        projectId={projectId}
        columns={columns}
        revision={tracker.data.definition.revision}
        onClose={() => {
          void navigate({ search: { new: undefined } });
        }}
      />
    </main>
  );
}
