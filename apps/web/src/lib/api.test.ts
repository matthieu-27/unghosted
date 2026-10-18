import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiDownload, apiFetch } from './api';
import { clearApiToken, fetchApiToken } from './api-token';

// The token module talks to the Better Auth server function; these tests
// cover the transport around it.
vi.mock('./api-token', () => ({
  fetchApiToken: vi.fn(),
  clearApiToken: vi.fn(),
}));

const fetchApiTokenMock = vi.mocked(fetchApiToken);
const clearApiTokenMock = vi.mocked(clearApiToken);

function mockFetch(status: number, body?: unknown) {
  const response = new Response(
    body === undefined ? null : JSON.stringify(body),
    { status, statusText: 'Status Text' },
  );
  return vi.fn().mockResolvedValue(response);
}

beforeEach(() => {
  fetchApiTokenMock.mockResolvedValue('test-token');
  clearApiTokenMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('apiFetch', () => {
  it('returns parsed JSON on success', async () => {
    const fetchMock = mockFetch(200, { data: [1, 2] });
    vi.stubGlobal('fetch', fetchMock);
    await expect(apiFetch('/projects')).resolves.toEqual({ data: [1, 2] });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/projects',
      expect.objectContaining({
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer test-token',
        },
      }),
    );
  });

  it('returns undefined on 204', async () => {
    vi.stubGlobal('fetch', mockFetch(204));
    await expect(apiFetch('/projects/x')).resolves.toBeUndefined();
  });

  it('throws ApiError with code and extra from the error body', async () => {
    vi.stubGlobal(
      'fetch',
      mockFetch(409, {
        detail: 'tracker moved on: rebase and retry',
        extra: { code: 'stale_revision', current_revision: 3 },
      }),
    );
    const error = await apiFetch('/projects/x/tracker/operations', {
      method: 'PATCH',
    }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(409);
    expect(apiError.code).toBe('stale_revision');
    expect(apiError.extra.current_revision).toBe(3);
    expect(apiError.message).toContain('rebase');
  });

  it('falls back to statusText on non-JSON error bodies', async () => {
    vi.stubGlobal('fetch', mockFetch(500));
    const error = (await apiFetch('/projects').catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(500);
    expect(error.code).toBeUndefined();
  });

  it('omits the JSON Content-Type for a FormData body', async () => {
    const fetchMock = mockFetch(201, { id: 'd1' });
    vi.stubGlobal('fetch', fetchMock);
    const form = new FormData();
    form.append('type_key', 'cv');
    await apiFetch('/projects/p1/documents', { method: 'POST', body: form });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).toEqual({ Authorization: 'Bearer test-token' });
  });

  it('sends no Authorization header when no session exists', async () => {
    fetchApiTokenMock.mockResolvedValue(null);
    const fetchMock = mockFetch(401, { detail: 'missing bearer token' });
    vi.stubGlobal('fetch', fetchMock);
    await apiFetch('/projects').catch(() => undefined);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
  });

  it('retries once with a fresh token after a 401', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: [] }), { status: 200 }),
      );
    vi.stubGlobal('fetch', fetchMock);
    fetchApiTokenMock
      .mockResolvedValueOnce('stale-token')
      .mockResolvedValueOnce('fresh-token');

    await expect(apiFetch('/projects')).resolves.toEqual({ data: [] });
    expect(clearApiTokenMock).toHaveBeenCalledTimes(1);
    const retryInit = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(retryInit.headers).toMatchObject({
      Authorization: 'Bearer fresh-token',
    });
  });

  it('surfaces a second 401 as an ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'invalid token' }), {
          status: 401,
        }),
      ),
    );
    const error = (await apiFetch('/projects').catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
  });
});

describe('apiDownload', () => {
  it('returns the blob and the server-named filename', async () => {
    const response = new Response('%PDF', {
      status: 200,
      headers: {
        'Content-Disposition': 'attachment; filename="renamed-cv.pdf"',
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal('fetch', fetchMock);
    const result = await apiDownload('/projects/p1/documents/d1/download');
    expect(result.filename).toBe('renamed-cv.pdf');
    expect(await result.blob.text()).toBe('%PDF');
  });

  it('returns a null filename when the header is absent', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('%PDF', { status: 200 })),
    );
    const result = await apiDownload('/projects/p1/documents/d1/download');
    expect(result.filename).toBeNull();
  });

  it('throws ApiError on a failed download', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(null, { status: 404, statusText: 'Not Found' }),
        ),
    );
    const error = (await apiDownload(
      '/projects/p1/documents/missing/download',
    ).catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
  });
});
