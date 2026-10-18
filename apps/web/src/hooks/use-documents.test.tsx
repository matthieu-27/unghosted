import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useDeleteDocument,
  useDocuments,
  useUploadDocument,
} from './use-documents';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {},
  apiFetch: apiFetchMock,
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  apiFetchMock.mockReset();
});

describe('useDocuments', () => {
  it('lists the documents of a project', async () => {
    apiFetchMock.mockResolvedValue({ data: [{ id: 'd1' }] });
    const { result } = renderHook(() => useDocuments('p1'), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual([{ id: 'd1' }]));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/documents');
  });
});

describe('useUploadDocument', () => {
  it('uploads a file as multipart form data', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useUploadDocument('p1'), { wrapper });
    const file = new File(['%PDF'], 'cv.pdf', { type: 'application/pdf' });
    result.current.mutate({ file, typeKey: 'cv' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [path, init] = apiFetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe('/projects/p1/documents');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('type_key')).toBe('cv');
    expect((init.body as FormData).get('file')).toBe(file);
  });
});

describe('useDeleteDocument', () => {
  it('deletes a document by id', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteDocument('p1'), { wrapper });
    result.current.mutate('d1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/documents/d1', {
      method: 'DELETE',
    });
  });
});
