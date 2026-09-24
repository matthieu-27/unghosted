/** Link-analysis mutation: paste in, pre-filled form data out (us-3). */

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import type { LinkAnalysisBody, LinkAnalysisResult } from '@/lib/tracker-types';

export function useLinkAnalysis(projectId: string) {
  return useMutation({
    mutationFn: (body: LinkAnalysisBody) =>
      apiFetch<LinkAnalysisResult>(`/projects/${projectId}/link-analyses`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  });
}
