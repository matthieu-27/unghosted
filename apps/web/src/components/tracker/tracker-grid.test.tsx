/** The contact-link column inside the grid (us-7 item 2): the cells
 * resolve against the contacts the route passes down. */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Contact } from '@/lib/contact-types';
import type { TrackerRow } from '@/lib/tracker-types';
import { TrackerGrid } from './tracker-grid';

// jsdom reports no scroll height, so the virtualizer would slice the body
// to nothing. It is mocked with the plain row list — the rows under test
// are the real component's, only the windowing is stubbed.
vi.mock('@tanstack/react-virtual', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@tanstack/react-virtual')>();
  return {
    ...actual,
    useVirtualizer: ({ count }: { count: number }) => ({
      getVirtualItems: () =>
        Array.from({ length: count }, (_, index) => ({
          index,
          key: index,
          start: index * 32,
          size: 32,
        })),
      getTotalSize: () => count * 32,
    }),
  };
});

afterEach(cleanup);

const CONTACTS: Contact[] = [
  {
    id: 'c1',
    name: 'Martin Dupont',
    role: null,
    organization: null,
    email: null,
    phone: null,
    profile_url: null,
    notes: null,
    linked_row_count: 0,
    created_at: '2026-09-24T10:00:00+00:00',
    updated_at: '2026-09-24T10:00:00+00:00',
  },
];

const COLUMNS = [
  { key: 'contact', type: 'contact-link', label: 'Contact' },
] as const;

const ROWS: TrackerRow[] = [
  { id: 'r1', order_key: 'r1', cells: { contact: ['c1'] } },
];

describe('TrackerGrid contact-link column', () => {
  it('resolves the ids against the contacts it is given', () => {
    render(
      <TrackerGrid
        columns={[...COLUMNS]}
        rows={ROWS}
        contacts={CONTACTS}
        onOperation={() => {}}
        onAddRow={() => {}}
        onDeleteRow={() => {}}
      />,
    );
    expect(screen.getByText('Martin Dupont')).toBeTruthy();
  });
});
