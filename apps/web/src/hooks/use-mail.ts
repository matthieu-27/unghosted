/** Mail queries and mutations (us-5). */

import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import type {
  ApprovedLetter,
  DraftUpdateBody,
  FirstContactDraftBody,
  LetterDraftBody,
  MailDraft,
  SendBody,
  SentEmail,
  SentMessageList,
} from '@/lib/mail-types';
import { queryKeys } from '@/lib/query-keys';

/** Prime the draft query cache so the editor opens without a refetch. */
function primeDraft(
  client: QueryClient,
  projectId: string,
  draft: MailDraft,
): void {
  client.setQueryData(queryKeys.mailDraft(projectId, draft.id), draft);
}

export function useMailDraft(projectId: string, draftId: string | null) {
  return useQuery({
    queryKey: queryKeys.mailDraft(projectId, draftId ?? 'none'),
    queryFn: () =>
      apiFetch<MailDraft>(`/projects/${projectId}/drafts/${draftId}`),
    enabled: draftId !== null,
  });
}

export function useDraftLetter(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { rowId: string; body: LetterDraftBody }) =>
      apiFetch<MailDraft>(`/projects/${projectId}/rows/${input.rowId}/letter`, {
        method: 'POST',
        body: JSON.stringify(input.body),
      }),
    onSuccess: (draft) => primeDraft(client, projectId, draft),
  });
}

export function useDraftFirstContact(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { rowId: string; body: FirstContactDraftBody }) =>
      apiFetch<MailDraft>(
        `/projects/${projectId}/rows/${input.rowId}/first-contact`,
        { method: 'POST', body: JSON.stringify(input.body) },
      ),
    onSuccess: (draft) => primeDraft(client, projectId, draft),
  });
}

export function useUpdateDraft(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; body: DraftUpdateBody }) =>
      apiFetch<MailDraft>(`/projects/${projectId}/drafts/${input.draftId}`, {
        method: 'PATCH',
        body: JSON.stringify(input.body),
      }),
    onSuccess: (draft) => primeDraft(client, projectId, draft),
  });
}

export function useApproveLetterDraft(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) =>
      apiFetch<ApprovedLetter>(
        `/projects/${projectId}/drafts/${draftId}/approve`,
        { method: 'POST' },
      ),
    onSuccess: (result) => {
      primeDraft(client, projectId, result.draft);
      // The letter becomes a project document.
      void client.invalidateQueries({
        queryKey: queryKeys.documents(projectId),
      });
    },
  });
}

export function useDiscardDraft(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) =>
      apiFetch<MailDraft>(`/projects/${projectId}/drafts/${draftId}/discard`, {
        method: 'POST',
      }),
    onSuccess: (draft) => primeDraft(client, projectId, draft),
  });
}

/** Sends and records one email. The row revision changes too, so the tracker
 * query is invalidated instead of patched. */
export function useSendDraft(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { draftId: string; body: SendBody }) =>
      apiFetch<SentEmail>(
        `/projects/${projectId}/drafts/${input.draftId}/send`,
        {
          method: 'POST',
          body: JSON.stringify(input.body),
        },
      ),
    onSuccess: (sent) => {
      void client.invalidateQueries({
        queryKey: queryKeys.tracker(projectId),
      });
      void client.invalidateQueries({
        queryKey: queryKeys.sentMessages(projectId),
      });
      void client.invalidateQueries({
        queryKey: queryKeys.mailDraft(projectId, sent.draft_id),
      });
    },
  });
}

export function useSentMessages(projectId: string) {
  return useQuery({
    queryKey: queryKeys.sentMessages(projectId),
    queryFn: () => apiFetch<SentMessageList>(`/projects/${projectId}/sent`),
    select: (list) => list.data,
  });
}
