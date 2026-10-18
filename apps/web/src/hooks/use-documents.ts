/** Document queries and mutations (us-4 items 1, 2, 4). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDownload, apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { DocumentList } from '@/lib/tracker-types';

export function useDocuments(projectId: string) {
  return useQuery({
    queryKey: queryKeys.documents(projectId),
    queryFn: () => apiFetch<DocumentList>(`/projects/${projectId}/documents`),
    select: (list) => list.data,
  });
}

export function useUploadDocument(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; typeKey: string }) => {
      // The browser sets the multipart Content-Type including the boundary.
      const form = new FormData();
      form.append('file', input.file);
      form.append('type_key', input.typeKey);
      return apiFetch<void>(`/projects/${projectId}/documents`, {
        method: 'POST',
        body: form,
      });
    },
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: queryKeys.documents(projectId),
      });
    },
  });
}

export function useDeleteDocument(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) =>
      apiFetch<void>(`/projects/${projectId}/documents/${documentId}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: queryKeys.documents(projectId),
      });
    },
  });
}

/** Streams the decrypted file through the API and saves it locally (us-4
 * item 4: no presigned URLs, the download is ownership-checked). */
export async function downloadDocument(
  projectId: string,
  documentId: string,
  fallbackName: string,
): Promise<void> {
  const { blob, filename } = await apiDownload(
    `/projects/${projectId}/documents/${documentId}/download`,
  );
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename ?? fallbackName;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
