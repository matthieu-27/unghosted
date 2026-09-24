/** Account creation page (user stories, section 6, item 1). */

import { createFileRoute, Link, redirect } from '@tanstack/react-router';

import { SignupForm } from '@/components/auth/signup-form';
import { getSession } from '@/lib/auth-server';

export const Route = createFileRoute('/signup')({
  beforeLoad: async () => {
    const user = await getSession();
    if (user) {
      throw redirect({ to: '/projects' });
    }
  },
  component: SignupPage,
});

function SignupPage() {
  return (
    <main className="mx-auto w-full max-w-sm p-6 pt-16">
      <h1 className="text-xl font-semibold">Create your account</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        One account, every search you are running.
      </p>
      <div className="mt-6">
        <SignupForm />
      </div>
      <p className="mt-6 text-sm text-muted-foreground">
        Already registered?{' '}
        <Link to="/login" className="underline">
          Sign in
        </Link>
      </p>
    </main>
  );
}
