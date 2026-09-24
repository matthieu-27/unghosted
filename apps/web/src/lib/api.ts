/**
 * The one API client. Every request carries the Better Auth JWT minted by
 * `lib/api-token`; no other module may touch tokens (ADR 0002, ADR 0003).
 */

import { clearApiToken, fetchApiToken } from '@/lib/api-token';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
    readonly extra: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function parseError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  let code: string | undefined;
  let extra: Record<string, unknown> = {};
  try {
    const body = (await response.json()) as {
      detail?: unknown;
      extra?: Record<string, unknown>;
    };
    if (typeof body.detail === 'string') detail = body.detail;
    if (body.extra && typeof body.extra === 'object') {
      extra = body.extra;
      const codeInExtra = body.extra.code;
      if (typeof codeInExtra === 'string') code = codeInExtra;
    }
  } catch {
    // Non-JSON error body: keep statusText.
  }
  return new ApiError(response.status, code, detail, extra);
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  // A FormData body must not get the JSON Content-Type: the browser sets the
  // multipart boundary, and overwriting it breaks multipart parsing.
  const isFormData =
    typeof FormData !== 'undefined' && init?.body instanceof FormData;

  const request = async (token: string | null): Promise<Response> =>
    fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    });

  const response = await request(await fetchApiToken());
  if (response.status !== 401) {
    return response;
  }
  // The token expired or the keys rotated: mint a fresh one and retry once.
  // A second 401 is a real authentication failure and surfaces as ApiError.
  clearApiToken();
  return request(await fetchApiToken());
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await send(path, init);
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Downloads a binary resource. Returns the blob and the server-named file. */
export async function apiDownload(
  path: string,
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await send(path);
  if (!response.ok) {
    throw await parseError(response);
  }
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^";]+)"?/);
  return {
    blob: await response.blob(),
    filename: match?.[1] ?? null,
  };
}
