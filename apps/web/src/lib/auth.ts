import { betterAuth } from 'better-auth';
import { jwt } from 'better-auth/plugins';
import { tanstackStartCookies } from 'better-auth/tanstack-start';
import { Pool } from 'pg';

/**
 * Better Auth instance mounted on the TanStack Start server (ADR 0002).
 * It owns sessions in the PostgreSQL `auth` schema and issues the
 * short-lived JWTs the Python API verifies against `/api/auth/jwks`.
 * Never import this file from client code.
 */

const baseUrl = process.env.BETTER_AUTH_URL ?? 'http://localhost:3000';

export const auth = betterAuth({
  database: new Pool({
    connectionString: process.env.DATABASE_URL,
    // Better Auth's tables live in their own schema: the Python API never
    // reads them, and Alembic never migrates them.
    options: '-c search_path=auth',
  }),
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: baseUrl,
  emailAndPassword: {
    enabled: true,
  },
  advanced: {
    database: {
      // Every `owner_user_id` in the API is a UUID. Better Auth's default
      // random string ids would not parse as one.
      generateId: 'uuid',
    },
  },
  rateLimit: {
    enabled: true,
    window: 60,
    max: 100,
    customRules: {
      '/sign-in/email': { window: 60, max: 5 },
      '/sign-up/email': { window: 60, max: 5 },
    },
  },
  plugins: [
    jwt({
      jwt: {
        issuer: baseUrl,
        audience: baseUrl,
        // Short-lived on purpose: a revoked session dies with its token.
        expirationTime: '15m',
        definePayload: ({ user }) => ({ email: user.email }),
      },
    }),
    // Must stay last: it wraps the handlers that set cookies.
    tanstackStartCookies(),
  ],
});
