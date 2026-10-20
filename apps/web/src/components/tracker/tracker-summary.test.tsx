/** TrackerSummary: the numbers on the cards are derived in tracker-stats
 * (pure, tested there); these tests pin the rendering. */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Distribution } from '@/lib/tracker-stats';
import { TrackerSummary } from './tracker-summary';

afterEach(cleanup);

const SELECT_DISTRIBUTION: Distribution = {
  column: {
    key: 'status',
    type: 'select',
    label: 'Status',
    options: [
      { key: 'sent', label: 'Sent' },
      { key: 'replied', label: 'Replied' },
    ],
  },
  entries: [
    { key: 'sent', label: 'Sent', count: 2, color: null },
    { key: 'replied', label: 'Replied', count: 0, color: null },
  ],
};

describe('TrackerSummary', () => {
  it('shows the row count and the completeness arithmetic', () => {
    render(
      <TrackerSummary
        rowCount={12}
        distribution={{ column: undefined, entries: [] }}
        fill={{ filled: 9, total: 12 }}
      />,
    );
    expect(screen.getByText('12')).toBeTruthy();
    expect(screen.getByText('75%')).toBeTruthy();
    expect(screen.getByText('9 of 12 cells filled')).toBeTruthy();
  });

  it('names the distribution card after the select column', () => {
    render(
      <TrackerSummary
        rowCount={2}
        distribution={SELECT_DISTRIBUTION}
        fill={{ filled: 2, total: 4 }}
      />,
    );
    expect(screen.getAllByText('Status').length).toBeGreaterThan(0);
  });

  it('suggests a select column when the tracker has none', () => {
    render(
      <TrackerSummary
        rowCount={0}
        distribution={{ column: undefined, entries: [] }}
        fill={{ filled: 0, total: 0 }}
      />,
    );
    expect(
      screen.getByText('Add a select column to see its distribution here.'),
    ).toBeTruthy();
  });
});
