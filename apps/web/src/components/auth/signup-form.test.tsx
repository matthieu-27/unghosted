import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  signUpEmail: vi.fn(),
  navigate: vi.fn(),
  invalidate: vi.fn(),
}));

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => h.navigate,
  useRouter: () => ({ invalidate: h.invalidate }),
}));

vi.mock('@/lib/auth-client', () => ({
  signUp: { email: h.signUpEmail },
}));

import { SignupForm } from './signup-form';

beforeEach(() => {
  h.signUpEmail.mockReset().mockResolvedValue({ error: null });
  h.navigate.mockReset().mockResolvedValue(undefined);
  h.invalidate.mockReset().mockResolvedValue(undefined);
});

afterEach(cleanup);

function fillValidForm() {
  fireEvent.change(screen.getByLabelText('Name'), {
    target: { value: 'Ada' },
  });
  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'ada@example.com' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'analytical-engine' },
  });
}

describe('SignupForm', () => {
  it('creates the account and lands on the dashboard', async () => {
    render(<SignupForm />);
    fillValidForm();
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() =>
      expect(h.signUpEmail).toHaveBeenCalledWith({
        name: 'Ada',
        email: 'ada@example.com',
        password: 'analytical-engine',
      }),
    );
    await waitFor(() =>
      expect(h.navigate).toHaveBeenCalledWith({ to: '/projects' }),
    );
  });

  it('explains a duplicate email in plain words', async () => {
    h.signUpEmail.mockResolvedValue({
      error: { code: 'USER_ALREADY_EXISTS', message: 'User already exists' },
    });
    render(<SignupForm />);
    fillValidForm();
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toBe(
        'An account already uses this email address.',
      ),
    );
  });

  it('rejects a password shorter than eight characters', async () => {
    render(<SignupForm />);
    fillValidForm();
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'short' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() =>
      expect(
        screen.getByText('Password must be at least 8 characters'),
      ).toBeDefined(),
    );
    expect(h.signUpEmail).not.toHaveBeenCalled();
  });
});
