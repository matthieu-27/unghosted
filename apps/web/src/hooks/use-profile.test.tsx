import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useApproveProfileVersion,
  useDraftProfile,
  useEditProfileVersion,
  useProfileState,
} from './use-profile';

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

describe('useProfileState', () => {
  it('fetches the profile state of a project', async () => {
    apiFetchMock.mockResolvedValue({
      approved: null,
      draft: null,
      versions: [],
    });
    const { result } = renderHook(() => useProfileState('p1'), { wrapper });
    await waitFor(() => expect(result.current.data?.versions).toEqual([]));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/profile');
  });
});

describe('useDraftProfile', () => {
  it('posts a draft request', async () => {
    apiFetchMock.mockResolvedValue({ version: 1, status: 'draft' });
    const { result } = renderHook(() => useDraftProfile('p1'), { wrapper });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/projects/p1/profile/drafts', {
      method: 'POST',
    });
  });
});

describe('useEditProfileVersion', () => {
  it('patches the edited fields of a draft version', async () => {
    apiFetchMock.mockResolvedValue({ version: 1, status: 'draft' });
    const { result } = renderHook(() => useEditProfileVersion('p1'), {
      wrapper,
    });
    result.current.mutate({
      version: 1,
      body: { headline: 'Tuned', highlights: [{ id: 'h1', text: 'Kept' }] },
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/projects/p1/profile/versions/1',
      {
        method: 'PATCH',
        body: JSON.stringify({
          headline: 'Tuned',
          highlights: [{ id: 'h1', text: 'Kept' }],
        }),
      },
    );
  });
});

describe('useApproveProfileVersion', () => {
  it('approves a draft version', async () => {
    apiFetchMock.mockResolvedValue({ version: 1, status: 'approved' });
    const { result } = renderHook(() => useApproveProfileVersion('p1'), {
      wrapper,
    });
    result.current.mutate(1);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/projects/p1/profile/versions/1/approve',
      { method: 'POST' },
    );
  });
});
