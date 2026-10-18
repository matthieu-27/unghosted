/**
 * Guard layout: everything under it needs a session (user stories, section
 * 6, item 2). Unauthenticated visitors land on /login with the URL they
 * wanted, so signing in can take them back there.
 */

import { createFileRoute, Outlet, redirect } from '@tanstack/react-router';

import { UserMenu } from '@/components/auth/user-menu';
import { getSession } from '@/lib/auth-server';

export const Route = createFileRoute('/_authed')({
  beforeLoad: async ({ location }) => {
    const user = await getSession();
    if (!user) {
      throw redirect({ to: '/login', search: { redirect: location.href } });
    }
    return { user };
  },
  component: AuthedLayout,
});

function AuthedLayout() {
  const { user } = Route.useRouteContext();

  return (
    <>
      <header className="flex justify-end border-b px-4 py-2">
        <UserMenu email={user.email} />
      </header>
      <Outlet />
    </>
  );
}
