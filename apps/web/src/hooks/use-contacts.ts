/** Contact queries and mutations (us-7 item 1). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import type {
  ContactDetail,
  ContactInput,
  ContactList,
} from '@/lib/contact-types';
import { queryKeys } from '@/lib/query-keys';

function listPath(projectId: string, search: string): string {
  const suffix = search ? `?search=${encodeURIComponent(search)}` : '';
  return `/projects/${projectId}/contacts${suffix}`;
}

/** Contacts of one project, optionally filtered by the search box. The
 * term is part of the cache key, so each term keeps its own result. */
export function useContacts(projectId: string, search = '') {
  return useQuery({
    queryKey: queryKeys.contacts(projectId, search),
    queryFn: () => apiFetch<ContactList>(listPath(projectId, search)),
    select: (list) => list.data,
  });
}

/** The detail panel payload: the contact, its linked rows, its threads. */
export function useContact(projectId: string, contactId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.contact(projectId, contactId ?? ''),
    queryFn: () =>
      apiFetch<ContactDetail>(`/projects/${projectId}/contacts/${contactId}`),
    enabled: contactId !== undefined,
  });
}

/** Every contact mutation invalidates the whole contacts subtree: the list
 * is cached per search term, and a rename changes which terms match. */
function useInvalidateContacts(projectId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({
      queryKey: ['projects', projectId, 'contacts'],
    });
  };
}

export function useCreateContact(projectId: string) {
  const invalidate = useInvalidateContacts(projectId);
  return useMutation({
    mutationFn: (input: ContactInput) =>
      apiFetch<void>(`/projects/${projectId}/contacts`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: invalidate,
  });
}

export function useUpdateContact(projectId: string) {
  const invalidate = useInvalidateContacts(projectId);
  return useMutation({
    mutationFn: (input: { contactId: string; changes: ContactInput }) =>
      apiFetch<void>(`/projects/${projectId}/contacts/${input.contactId}`, {
        method: 'PATCH',
        body: JSON.stringify(input.changes),
      }),
    onSuccess: invalidate,
  });
}

export function useDeleteContact(projectId: string) {
  const client = useQueryClient();
  const invalidate = useInvalidateContacts(projectId);
  return useMutation({
    mutationFn: (contactId: string) =>
      apiFetch<void>(`/projects/${projectId}/contacts/${contactId}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      invalidate();
      // The server clears the deleted id from the contact-link cells
      // (us-7 item 3), so the cached tracker is stale too.
      void client.invalidateQueries({ queryKey: queryKeys.tracker(projectId) });
    },
  });
}
