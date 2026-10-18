/** Public landing: the door to sign in or sign up. */

import { createFileRoute, Link, redirect } from '@tanstack/react-router';

import { getSession } from '@/lib/auth-server';

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    const user = await getSession();
    if (user) {
      throw redirect({ to: '/projects' });
    }
  },
  component: LandingPage,
});

function LandingPage() {
  return (
    <main className="mx-auto w-full max-w-md p-6 pt-24">
      <h1 className="text-2xl font-semibold">Unghosted</h1>
      <p className="mt-2 text-muted-foreground">
        Track every application, know where each one stands, and write the next
        message without leaving the page.
      </p>
      <div className="mt-8 flex gap-3">
        <Link
          to="/signup"
          className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
        >
          Create an account
        </Link>
        <Link to="/login" className="rounded-md border px-4 py-2 text-sm">
          Sign in
        </Link>
      </div>
    </main>
  );
}
