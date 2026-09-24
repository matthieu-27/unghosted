import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  signInEmail: vi.fn(),
  navigate: vi.fn(),
  invalidate: vi.fn(),
}));

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => h.navigate,
  useRouter: () => ({ invalidate: h.invalidate }),
}));

vi.mock('@/lib/auth-client', () => ({
  signIn: { email: h.signInEmail },
}));

import { LoginForm } from './login-form';

beforeEach(() => {
  h.signInEmail.mockReset().mockResolvedValue({ error: null });
  h.navigate.mockReset().mockResolvedValue(undefined);
  h.invalidate.mockReset().mockResolvedValue(undefined);
});

afterEach(cleanup);

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('LoginForm', () => {
  it('signs the user in and sends them to the dashboard', async () => {
    render(<LoginForm redirectTo={undefined} />);
    fill('Email', 'user@example.com');
    fill('Password', 'correct horse battery');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(h.signInEmail).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'correct horse battery',
      }),
    );
    await waitFor(() =>
      expect(h.navigate).toHaveBeenCalledWith({ to: '/projects' }),
    );
  });

  it('shows one message for wrong credentials and stays put', async () => {
    h.signInEmail.mockResolvedValue({
      error: { code: 'INVALID_EMAIL_OR_PASSWORD' },
    });
    render(<LoginForm redirectTo={undefined} />);
    fill('Email', 'user@example.com');
    fill('Password', 'wrong');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toBe(
        'Email or password is incorrect.',
      ),
    );
    expect(h.navigate).not.toHaveBeenCalled();
  });

  it('returns the visitor to the page the guard interrupted', async () => {
    render(<LoginForm redirectTo="/projects/p1/tracker" />);
    fill('Email', 'user@example.com');
    fill('Password', 'correct horse battery');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(h.navigate).toHaveBeenCalledWith({
        href: '/projects/p1/tracker',
      }),
    );
  });

  it('refuses to submit an empty form', async () => {
    render(<LoginForm redirectTo={undefined} />);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() =>
      expect(screen.getByText('Email is required')).toBeDefined(),
    );
    expect(h.signInEmail).not.toHaveBeenCalled();
  });
});
