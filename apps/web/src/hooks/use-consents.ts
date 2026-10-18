/** Consent queries and mutations (us-4 item 5). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { ConsentList } from '@/lib/tracker-types';

export function useConsents() {
  return useQuery({
    queryKey: queryKeys.consents(),
    queryFn: () => apiFetch<ConsentList>('/account/consents'),
    select: (list) => list.data,
  });
}

export function useGrantConsent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (kind: string) =>
      apiFetch<void>('/account/consents', {
        method: 'POST',
        body: JSON.stringify({ kind }),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.consents() });
    },
  });
}

export function useWithdrawConsent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (kind: string) =>
      apiFetch<void>(`/account/consents/${kind}`, { method: 'DELETE' }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.consents() });
    },
  });
}
