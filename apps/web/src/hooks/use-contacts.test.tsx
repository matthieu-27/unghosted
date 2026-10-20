import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useContact,
  useContacts,
  useCreateContact,
  useDeleteContact,
  useUpdateContact,
} from './use-contacts';

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

describe('useContacts', () => {
  it('lists the contacts of a project', async () => {
    apiFetchMock.mockResolvedValue({ data: [{ id: 'c1' }] });
    const { result } = renderHook(() => useContacts('p1'), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual([{ id: 'c1' }]));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/contacts');
  });

  it('sends the search term as an encoded query parameter', async () => {
    apiFetchMock.mockResolvedValue({ data: [] });
    const { result } = renderHook(() => useContacts('p1', 'le dojo'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/projects/p1/contacts?search=le%20dojo',
    );
  });
});

describe('useContact', () => {
  it('stays idle until a contact is selected', async () => {
    const { result } = renderHook(() => useContact('p1', undefined), {
      wrapper,
    });
    // A disabled query never leaves isPending: fetchStatus is what moves.
    await waitFor(() => expect(result.current.fetchStatus).toBe('idle'));
    expect(apiFetchMock).not.toHaveBeenCalled();
  });

  it('reads the detail payload of the selected contact', async () => {
    apiFetchMock.mockResolvedValue({
      contact: { id: 'c1' },
      linked_row_ids: [],
      threads: [],
    });
    const { result } = renderHook(() => useContact('p1', 'c1'), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/contacts/c1');
  });
});

describe('useCreateContact', () => {
  it('posts the contact fields', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useCreateContact('p1'), { wrapper });
    result.current.mutate({ name: 'Martin', email: null });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/contacts', {
      method: 'POST',
      body: JSON.stringify({ name: 'Martin', email: null }),
    });
  });
});

describe('useUpdateContact', () => {
  it('patches only the changed fields', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useUpdateContact('p1'), { wrapper });
    result.current.mutate({ contactId: 'c1', changes: { role: 'Data lead' } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/contacts/c1', {
      method: 'PATCH',
      body: JSON.stringify({ role: 'Data lead' }),
    });
  });
});

describe('useDeleteContact', () => {
  it('deletes a contact by id', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useDeleteContact('p1'), { wrapper });
    result.current.mutate('c1');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/contacts/c1', {
      method: 'DELETE',
    });
  });
});
