import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MailDraft, SentMessageList } from '@/lib/mail-types';
import { queryKeys } from '@/lib/query-keys';
import {
  useApproveLetterDraft,
  useDiscardDraft,
  useDraftFirstContact,
  useDraftLetter,
  useMailDraft,
  useSendDraft,
  useSentMessages,
  useUpdateDraft,
} from './use-mail';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('@/lib/api', () => ({
  ApiError: class ApiError extends Error {},
  apiFetch: apiFetchMock,
}));

const PROJECT_ID = 'p1';
const DRAFT_ID = 'd1';

function draft(overrides: Partial<MailDraft> = {}): MailDraft {
  return {
    id: DRAFT_ID,
    kind: 'first_contact_email',
    status: 'draft',
    row_id: 'row-0',
    recipient: 'martin@dojoclub.example',
    contact_name: 'Martin',
    subject: 'Candidature',
    text: 'Bonjour Martin,',
    used_highlights: ['h1'],
    attachment_document_ids: [],
    letter_document_id: null,
    warnings: [],
    created_at: '2026-09-24T10:00:00Z',
    updated_at: '2026-09-24T10:00:00Z',
    ...overrides,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  apiFetchMock.mockReset();
});

describe('useMailDraft', () => {
  it('fetches the draft when an id is given', async () => {
    apiFetchMock.mockResolvedValue(draft());
    const { result } = renderHook(() => useMailDraft(PROJECT_ID, DRAFT_ID), {
      wrapper,
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/drafts/${DRAFT_ID}`,
    );
  });

  it('stays idle when the draft id is null', async () => {
    const { result } = renderHook(() => useMailDraft(PROJECT_ID, null), {
      wrapper,
    });
    // A disabled query keeps status pending, but the fetch stays idle.
    await waitFor(() => expect(result.current.fetchStatus).toBe('idle'));
    expect(apiFetchMock).not.toHaveBeenCalled();
  });
});

describe('useDraftLetter', () => {
  it('posts the row and seeds the draft cache from the response', async () => {
    apiFetchMock.mockResolvedValue(draft({ kind: 'customised_letter' }));
    const client = new QueryClient();
    const { result } = renderHook(() => useDraftLetter(PROJECT_ID), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });
    result.current.mutate({ rowId: 'row-0', body: {} });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() =>
      expect(
        client.getQueryData(queryKeys.mailDraft(PROJECT_ID, DRAFT_ID)),
      ).toMatchObject({ kind: 'customised_letter' }),
    );
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/rows/row-0/letter`,
      { method: 'POST', body: JSON.stringify({}) },
    );
  });
});

describe('useDraftFirstContact', () => {
  it('posts the recipient with the row', async () => {
    apiFetchMock.mockResolvedValue(draft());
    const { result } = renderHook(() => useDraftFirstContact(PROJECT_ID), {
      wrapper,
    });
    result.current.mutate({
      rowId: 'row-0',
      body: { recipient: 'martin@dojoclub.example' },
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/rows/row-0/first-contact`,
      {
        method: 'POST',
        body: JSON.stringify({ recipient: 'martin@dojoclub.example' }),
      },
    );
  });
});

describe('useUpdateDraft', () => {
  it('patches the changed fields', async () => {
    apiFetchMock.mockResolvedValue(draft({ text: 'Edited body' }));
    const { result } = renderHook(() => useUpdateDraft(PROJECT_ID), {
      wrapper,
    });
    result.current.mutate({ draftId: DRAFT_ID, body: { text: 'Edited body' } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/drafts/${DRAFT_ID}`,
      { method: 'PATCH', body: JSON.stringify({ text: 'Edited body' }) },
    );
  });
});

describe('useApproveLetterDraft', () => {
  it('posts the approval and seeds the returned draft', async () => {
    apiFetchMock.mockResolvedValue({
      draft: draft({ kind: 'customised_letter', status: 'approved' }),
      document_id: 'doc-1',
      fits_one_page: true,
    });
    const client = new QueryClient();
    const { result } = renderHook(() => useApproveLetterDraft(PROJECT_ID), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });
    result.current.mutate(DRAFT_ID);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() =>
      expect(
        client.getQueryData(queryKeys.mailDraft(PROJECT_ID, DRAFT_ID)),
      ).toMatchObject({ status: 'approved' }),
    );
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/drafts/${DRAFT_ID}/approve`,
      { method: 'POST' },
    );
  });
});

describe('useDiscardDraft', () => {
  it('discards the draft', async () => {
    apiFetchMock.mockResolvedValue(draft({ status: 'discarded' }));
    const { result } = renderHook(() => useDiscardDraft(PROJECT_ID), {
      wrapper,
    });
    result.current.mutate(DRAFT_ID);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/drafts/${DRAFT_ID}/discard`,
      { method: 'POST' },
    );
  });
});

describe('useSendDraft', () => {
  it('sends the draft as an empty update body', async () => {
    apiFetchMock.mockResolvedValue({
      message_id: 'm1',
      thread_id: 't1',
      draft_id: DRAFT_ID,
      sender: 'applicant@example.com',
      recipient: 'martin@dojoclub.example',
      subject: 'Candidature',
      provider: 'smtp',
      provider_message_id: null,
      provider_thread_id: null,
      attachment_document_ids: [],
      sent_at: '2026-09-24T10:05:00Z',
      row_revision: 3,
    });
    const { result } = renderHook(() => useSendDraft(PROJECT_ID), { wrapper });
    result.current.mutate({ draftId: DRAFT_ID, body: {} });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiFetchMock).toHaveBeenCalledWith(
      `/projects/${PROJECT_ID}/drafts/${DRAFT_ID}/send`,
      { method: 'POST', body: JSON.stringify({}) },
    );
  });
});

describe('useSentMessages', () => {
  it('lists the sent messages of the project', async () => {
    const list: SentMessageList = { data: [] };
    apiFetchMock.mockResolvedValue(list);
    const { result } = renderHook(() => useSentMessages(PROJECT_ID), {
      wrapper,
    });
    await waitFor(() => expect(result.current.data).toEqual([]));
    expect(apiFetchMock).toHaveBeenCalledWith(`/projects/${PROJECT_ID}/sent`);
  });
});
