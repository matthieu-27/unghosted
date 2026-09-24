/** Sign-in page (user stories, section 6, item 2). */

import { createFileRoute, Link, redirect } from '@tanstack/react-router';

import { LoginForm } from '@/components/auth/login-form';
import { getSession } from '@/lib/auth-server';

interface LoginSearch {
  redirect?: string;
}

/** Own paths only: an absolute or protocol-relative URL would let a crafted
 * link bounce a freshly signed-in user onto another site. */
function internalPath(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  if (!value.startsWith('/') || value.startsWith('//')) return undefined;
  return value;
}

export const Route = createFileRoute('/login')({
  validateSearch: (search: Record<string, unknown>): LoginSearch => ({
    redirect: internalPath(search.redirect),
  }),
  beforeLoad: async () => {
    const user = await getSession();
    if (user) {
      throw redirect({ to: '/projects' });
    }
  },
  component: LoginPage,
});

function LoginPage() {
  const { redirect: redirectTo } = Route.useSearch();

  return (
    <main className="mx-auto w-full max-w-sm p-6 pt-16">
      <h1 className="text-xl font-semibold">Sign in</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Your projects, trackers and mail live behind this door.
      </p>
      <div className="mt-6">
        <LoginForm redirectTo={redirectTo} />
      </div>
      <p className="mt-6 text-sm text-muted-foreground">
        No account yet?{' '}
        <Link to="/signup" className="underline">
          Create one
        </Link>
      </p>
    </main>
  );
}
