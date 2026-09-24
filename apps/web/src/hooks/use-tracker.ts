/** Tracker fetch hook: definition + rows + revision in one payload. */

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { TrackerPayload } from '@/lib/tracker-types';

export function useTracker(projectId: string) {
  return useQuery({
    queryKey: queryKeys.tracker(projectId),
    queryFn: () => apiFetch<TrackerPayload>(`/projects/${projectId}/tracker`),
  });
}
