/**
 * Signed-in identity and sign-out (user stories, section 6, item 2).
 * Signing out clears the cookie and the cached API token.
 */

import { useNavigate, useRouter } from '@tanstack/react-router';

import { Button } from '@/components/ui/button';
import { clearApiToken } from '@/lib/api-token';
import { signOut } from '@/lib/auth-client';

interface UserMenuProps {
  email: string;
}

export function UserMenu({ email }: UserMenuProps) {
  const navigate = useNavigate();
  const router = useRouter();

  const handleSignOut = async () => {
    await signOut();
    clearApiToken();
    await router.invalidate();
    await navigate({ to: '/login' });
  };

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-muted-foreground">{email}</span>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => {
          void handleSignOut();
        }}
      >
        Sign out
      </Button>
    </div>
  );
}
