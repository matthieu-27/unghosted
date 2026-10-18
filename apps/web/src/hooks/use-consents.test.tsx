import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useConsents,
  useGrantConsent,
  useWithdrawConsent,
} from './use-consents';

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

describe('useConsents', () => {
  it('lists the account consents', async () => {
    apiFetchMock.mockResolvedValue({
      data: [{ kind: 'model_processing', granted_at: 't', withdrawn_at: null }],
    });
    const { result } = renderHook(() => useConsents(), { wrapper });
    await waitFor(() =>
      expect(result.current.data?.[0]?.kind).toBe('model_processing'),
    );
    expect(apiFetchMock).toHaveBeenCalledWith('/account/consents');
  });
});

describe('useGrantConsent', () => {
  it('grants a consent kind', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useGrantConsent(), { wrapper });
    result.current.mutate('model_processing');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith('/account/consents', {
      method: 'POST',
      body: JSON.stringify({ kind: 'model_processing' }),
    });
  });
});

describe('useWithdrawConsent', () => {
  it('withdraws a consent kind', async () => {
    apiFetchMock.mockResolvedValue(undefined);
    const { result } = renderHook(() => useWithdrawConsent(), { wrapper });
    result.current.mutate('model_processing');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/account/consents/model_processing',
      { method: 'DELETE' },
    );
  });
});
