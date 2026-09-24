import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TrackerRow } from '@/lib/tracker-types';
import { useAutosave } from './use-autosave';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly code: string | undefined,
      message: string,
      readonly extra: Record<string, unknown> = {},
    ) {
      super(message);
    }
  },
  apiFetch: apiFetchMock,
}));

const serverRows: TrackerRow[] = [
  { id: 'row-1', order_key: 'k1', cells: { company: 'Acme' } },
];

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  apiFetchMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('useAutosave', () => {
  it('adopts server rows when there are no pending edits', async () => {
    const { result } = renderHook(() => useAutosave('p1', serverRows, 7), {
      wrapper,
    });
    await waitFor(() => expect(result.current.rows).toEqual(serverRows));
    expect(result.current.status).toBe('saved');
  });

  it('applies edits optimistically and flushes after the debounce', async () => {
    apiFetchMock.mockResolvedValue({ revision: 8, applied: [] });
    const { result } = renderHook(() => useAutosave('p1', serverRows, 7), {
      wrapper,
    });
    await waitFor(() => expect(result.current.rows).toEqual(serverRows));

    act(() => {
      result.current.push({
        op: 'set_cell',
        row_id: 'row-1',
        column_key: 'company',
        value: 'Bee Inc',
      });
    });
    expect(result.current.rows[0]?.cells.company).toBe('Bee Inc');
    expect(result.current.status).toBe('saved'); // not flushed yet
    expect(apiFetchMock).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/projects/p1/tracker/operations',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          base_revision: 7,
          operations: [
            {
              op: 'set_cell',
              row_id: 'row-1',
              column_key: 'company',
              value: 'Bee Inc',
            },
          ],
        }),
      }),
    );
    // Flush completed inside the timer advance: back to saved, edit persisted.
    await waitFor(() => expect(result.current.status).toBe('saved'));
  });

  it('marks conflict on a 409 and keeps pending cell edits for replay', async () => {
    apiFetchMock.mockRejectedValue(
      new (await import('@/lib/api')).ApiError(
        409,
        'stale_revision',
        'moved on',
      ),
    );
    const { result } = renderHook(() => useAutosave('p1', serverRows, 7), {
      wrapper,
    });
    await waitFor(() => expect(result.current.rows).toEqual(serverRows));

    act(() => {
      result.current.push({
        op: 'set_cell',
        row_id: 'row-1',
        column_key: 'company',
        value: 'Cmal',
      });
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    await waitFor(() => expect(result.current.status).toBe('conflict'));
  });
});
