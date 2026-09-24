/** Sent-mail list (us-5 item 6) tests. */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import type { SentMessage } from '@/lib/mail-types';
import { SentList } from './sent-list';

afterEach(cleanup);

function message(overrides: Partial<SentMessage> = {}): SentMessage {
  return {
    id: 'm1',
    thread_id: 't1',
    row_id: 'row-0',
    sender: 'applicant@example.com',
    recipient: 'martin@dojoclub.example',
    subject: 'Candidature',
    direction: 'outbound',
    provider: 'smtp',
    provider_message_id: null,
    attachment_document_ids: [],
    sent_at: '2026-09-24T10:05:00Z',
    text: 'Bonjour Martin,',
    ...overrides,
  };
}

describe('SentList', () => {
  it('user sees one row per sent message', () => {
    render(<SentList messages={[message()]} />);
    expect(screen.getByText('martin@dojoclub.example')).toBeTruthy();
    expect(screen.getByText('Candidature')).toBeTruthy();
  });

  it('user sees the empty state when nothing was sent', () => {
    render(<SentList messages={[]} />);
    expect(
      screen.getByText(
        'Nothing sent yet. A sent email appears here and updates its row.',
      ),
    ).toBeTruthy();
  });
});
