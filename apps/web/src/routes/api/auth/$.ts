import { createFileRoute } from '@tanstack/react-router';

import { auth } from '@/lib/auth';

/**
 * Catch-all server route delegating every /api/auth/* request to Better Auth,
 * per the official Better Auth TanStack Start integration.
 */
export const Route = createFileRoute('/api/auth/$')({
  server: {
    handlers: {
      GET: async ({ request }: { request: Request }) => auth.handler(request),
      POST: async ({ request }: { request: Request }) => auth.handler(request),
    },
  },
});
