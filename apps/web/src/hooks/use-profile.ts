/** Applicant-profile queries and mutations (us-4 item 3). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type {
  ProfileContentUpdateBody,
  ProfileState,
  ProfileVersion,
} from '@/lib/tracker-types';

export function useProfileState(projectId: string) {
  return useQuery({
    queryKey: queryKeys.profile(projectId),
    queryFn: () => apiFetch<ProfileState>(`/projects/${projectId}/profile`),
  });
}

export function useDraftProfile(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<ProfileVersion>(`/projects/${projectId}/profile/drafts`, {
        method: 'POST',
      }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: queryKeys.profile(projectId),
      });
    },
  });
}

export function useEditProfileVersion(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { version: number; body: ProfileContentUpdateBody }) =>
      apiFetch<ProfileVersion>(
        `/projects/${projectId}/profile/versions/${input.version}`,
        { method: 'PATCH', body: JSON.stringify(input.body) },
      ),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: queryKeys.profile(projectId),
      });
    },
  });
}

export function useApproveProfileVersion(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (version: number) =>
      apiFetch<ProfileVersion>(
        `/projects/${projectId}/profile/versions/${version}/approve`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: queryKeys.profile(projectId),
      });
    },
  });
}
