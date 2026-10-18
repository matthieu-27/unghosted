import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => {
  const mutation = () => ({
    isPending: false,
    error: null as Error | null,
    mutate: vi.fn(),
  });
  return {
    project: {} as Record<string, unknown>,
    tracker: {} as Record<string, unknown>,
    documents: { isError: false, isPending: false, data: [] },
    draft: {} as Record<string, unknown>,
    sent: { isError: false, isPending: false, data: [] },
    draftLetter: mutation(),
    draftFirstContact: mutation(),
    update: mutation(),
    approve: mutation(),
    discard: mutation(),
    send: mutation(),
  };
});

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => h.project,
}));

vi.mock('@/hooks/use-mail', () => ({
  useMailDraft: () => h.draft,
  useDraftLetter: () => h.draftLetter,
  useDraftFirstContact: () => h.draftFirstContact,
  useUpdateDraft: () => h.update,
  useApproveLetterDraft: () => h.approve,
  useDiscardDraft: () => h.discard,
  useSendDraft: () => h.send,
  useSentMessages: () => h.sent,
}));

vi.mock('@/hooks/use-documents', () => ({
  useDocuments: () => h.documents,
}));

vi.mock('@/hooks/use-tracker', () => ({
  useTracker: () => h.tracker,
}));

vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {
    constructor(
      readonly status: number,
      readonly code: string | undefined,
      message: string,
    ) {
      super(message);
    }
  },
  apiFetch: vi.fn(),
}));

import { MailPage, mailActionMessage } from '@/components/mail/mail-page';
import { ApiError } from '@/lib/api';

afterEach(cleanup);

beforeEach(() => {
  h.project = {
    isError: false,
    isPending: false,
    data: { id: 'p1', name: 'Test project' },
  };
  h.tracker = {
    isError: false,
    isPending: false,
    data: { rows: [{ id: 'row-0', cells: { company: 'Le Dojo Club' } }] },
  };
  h.draft = { isError: false, isPending: false, data: undefined };
});

function renderPage(overrides: Partial<Parameters<typeof MailPage>[0]> = {}) {
  const onOpenDraft = vi.fn();
  const onClearDraft = vi.fn();
  render(
    <MailPage
      projectId="p1"
      rowId="row-0"
      draftId={null}
      onOpenDraft={onOpenDraft}
      onClearDraft={onClearDraft}
      {...overrides}
    />,
  );
  return { onOpenDraft, onClearDraft };
}

describe('mailActionMessage', () => {
  it('user sees the mapped sentence for a known mail error code', () => {
    expect(
      mailActionMessage(
        new ApiError(409, 'recipient_cooldown', 'cooldown active'),
      ),
    ).toBe('An email went to this recipient less than 7 days ago.');
  });

  it('user sees the server detail for an unmapped ApiError code', () => {
    expect(
      mailActionMessage(new ApiError(400, 'other_code', 'Server detail')),
    ).toBe('Server detail');
  });

  it('user sees the message for a plain Error', () => {
    expect(mailActionMessage(new Error('boom'))).toBe('boom');
  });

  it('user sees nothing for a non-error value', () => {
    expect(mailActionMessage('nope')).toBeNull();
  });
});

describe('MailPage', () => {
  it('user sees the company of the selected row', () => {
    renderPage();
    expect(screen.getByText(/Le Dojo Club/)).toBeTruthy();
  });

  it('user starts a letter draft for the row', () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Draft letter' }));
    expect(h.draftLetter.mutate).toHaveBeenCalledWith(
      { rowId: 'row-0', body: {} },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it('user cannot draft a first contact without a recipient', () => {
    renderPage();
    expect(
      screen
        .getByRole('button', { name: 'Draft first contact' })
        .getAttribute('disabled'),
    ).not.toBeNull();
  });

  it('user starts a first-contact draft with the typed recipient', () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('First-contact recipient'), {
      target: { value: 'martin@dojoclub.example' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Draft first contact' }),
    );
    expect(h.draftFirstContact.mutate).toHaveBeenCalledWith(
      { rowId: 'row-0', body: { recipient: 'martin@dojoclub.example' } },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it('user sees an error when the project query fails', () => {
    h.project = { isError: true, isPending: false, data: undefined };
    renderPage();
    expect(screen.getByText('Cannot load project.')).toBeTruthy();
  });

  it('user sees an error when the draft query fails', () => {
    h.draft = { isError: true, isPending: false, data: undefined };
    renderPage({ draftId: 'd1' });
    expect(screen.getByText(/Cannot load draft/)).toBeTruthy();
  });

  it('user sees the mutation error while no draft is open', () => {
    h.draftLetter = {
      isPending: false,
      error: new ApiError(409, 'no_listing_text', 'detail'),
      mutate: vi.fn(),
    };
    renderPage();
    expect(
      screen.getByText(
        'This row has no analyzed listing. Run the listing analysis first.',
      ),
    ).toBeTruthy();
  });
});
