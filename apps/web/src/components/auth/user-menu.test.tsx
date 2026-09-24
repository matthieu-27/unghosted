import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  signOut: vi.fn(),
  clearApiToken: vi.fn(),
  navigate: vi.fn(),
  invalidate: vi.fn(),
}));

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => h.navigate,
  useRouter: () => ({ invalidate: h.invalidate }),
}));

vi.mock('@/lib/auth-client', () => ({ signOut: h.signOut }));
vi.mock('@/lib/api-token', () => ({ clearApiToken: h.clearApiToken }));

import { UserMenu } from './user-menu';

beforeEach(() => {
  h.signOut.mockReset().mockResolvedValue(undefined);
  h.clearApiToken.mockReset();
  h.navigate.mockReset().mockResolvedValue(undefined);
  h.invalidate.mockReset().mockResolvedValue(undefined);
});

afterEach(cleanup);

describe('UserMenu', () => {
  it('shows the signed-in email', () => {
    render(<UserMenu email="ada@example.com" />);
    expect(screen.getByText('ada@example.com')).toBeDefined();
  });

  it('signs out, drops the cached token and goes to the login page', async () => {
    render(<UserMenu email="ada@example.com" />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(h.signOut).toHaveBeenCalledTimes(1));
    expect(h.clearApiToken).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(h.navigate).toHaveBeenCalledWith({ to: '/login' }),
    );
  });
});
