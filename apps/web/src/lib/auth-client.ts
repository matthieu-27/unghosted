import { createAuthClient } from 'better-auth/react';

/**
 * Browser-side Better Auth client. Sessions travel in httpOnly cookies, so
 * nothing here reads or stores a credential (ADR 0002).
 */
export const authClient = createAuthClient();

export const { signIn, signUp, signOut, useSession } = authClient;
