import { createServerFn } from '@tanstack/react-start';
import { getRequestHeaders } from '@tanstack/react-start/server';

import { auth } from '@/lib/auth';

export interface SessionUser {
  id: string;
  email: string;
  name: string;
}

/**
 * Reads the Better Auth session from the request cookies. Returns null when
 * nobody is signed in — route guards decide what to do with that.
 */
export const getSession = createServerFn({ method: 'GET' }).handler(
  async (): Promise<SessionUser | null> => {
    const session = await auth.api.getSession({ headers: getRequestHeaders() });
    if (!session) return null;
    return {
      id: session.user.id,
      email: session.user.email,
      name: session.user.name,
    };
  },
);

/**
 * Mints a short-lived JWT for the Python API (ADR 0002). Runs on the server
 * so the session cookie never has to be readable by client code.
 */
export const getApiToken = createServerFn({ method: 'GET' }).handler(
  async (): Promise<string | null> => {
    const headers = getRequestHeaders();
    const session = await auth.api.getSession({ headers });
    if (!session) return null;
    const { token } = await auth.api.getToken({ headers });
    return token;
  },
);
