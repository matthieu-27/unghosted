import { betterAuth } from 'better-auth';
import { Pool } from 'pg';

/**
 * Better Auth instance mounted on the TanStack Start server.
 * Phase 0: minimal wiring to prove the integration runs on Bun.
 * Phase 2 adds the JWT plugin, the `auth` schema configuration, and
 * email/password options. Never import this file from client code.
 */
export const auth = betterAuth({
  database: new Pool({
    connectionString: process.env.DATABASE_URL,
  }),
  secret: process.env.BETTER_AUTH_SECRET,
});
