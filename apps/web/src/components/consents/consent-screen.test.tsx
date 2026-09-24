import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ConsentScreen } from './consent-screen';

afterEach(cleanup);

function renderScreen(
  overrides: Partial<Parameters<typeof ConsentScreen>[0]> = {},
) {
  const onGrant = vi.fn();
  const onWithdraw = vi.fn();
  render(
    <ConsentScreen
      granted={false}
      granting={false}
      error={null}
      onGrant={onGrant}
      onWithdraw={onWithdraw}
      {...overrides}
    />,
  );
  return { onGrant, onWithdraw };
}

describe('ConsentScreen', () => {
  it('shows the grant button when consent is not granted', () => {
    const { onGrant } = renderScreen();
    fireEvent.click(
      screen.getByRole('button', { name: 'Allow model processing' }),
    );
    expect(onGrant).toHaveBeenCalledOnce();
  });

  it('shows the withdraw button when consent is granted', () => {
    const { onWithdraw } = renderScreen({ granted: true });
    fireEvent.click(screen.getByRole('button', { name: 'Withdraw consent' }));
    expect(onWithdraw).toHaveBeenCalledOnce();
  });

  it('disables the grant button while granting', () => {
    renderScreen({ granting: true });
    expect(
      screen
        .getByRole('button', { name: 'Granting…' })
        .hasAttribute('disabled'),
    ).toBe(true);
  });

  it('shows the action error', () => {
    renderScreen({ error: 'Grant model-processing consent first.' });
    expect(screen.getByRole('alert').textContent).toContain(
      'Grant model-processing consent first.',
    );
  });
});
