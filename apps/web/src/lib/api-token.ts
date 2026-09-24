import { getApiToken } from '@/lib/auth-server';

/**
 * The only place an API token lives (ADR 0002, ADR 0003). Tokens are held in
 * this module's closure — never in localStorage, never in a component.
 *
 * Better Auth issues 15-minute tokens. The cache is dropped a minute early so
 * a request never leaves with a token that expires in flight, and `clear()`
 * lets the API client retry once after a 401.
 */

const REFRESH_MARGIN_MS = 60_000;
const TOKEN_LIFETIME_MS = 15 * 60_000;

let cached: { token: string; expiresAt: number } | null = null;
let inFlight: Promise<string | null> | null = null;

export function clearApiToken(): void {
  cached = null;
  inFlight = null;
}

export async function fetchApiToken(): Promise<string | null> {
  if (cached && cached.expiresAt > Date.now()) {
    return cached.token;
  }
  // Concurrent callers share one round trip.
  inFlight ??= getApiToken()
    .then((token) => {
      cached = token
        ? {
            token,
            expiresAt: Date.now() + TOKEN_LIFETIME_MS - REFRESH_MARGIN_MS,
          }
        : null;
      return token;
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}
