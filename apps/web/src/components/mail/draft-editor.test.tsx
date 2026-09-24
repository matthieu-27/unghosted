import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { MailDraft } from '@/lib/mail-types';
import { DraftEditor } from './draft-editor';

afterEach(cleanup);

function draft(overrides: Partial<MailDraft> = {}): MailDraft {
  return {
    id: 'd1',
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

function renderEditor(
  draftValue: MailDraft,
  overrides: Partial<Parameters<typeof DraftEditor>[0]> = {},
) {
  const onSave = vi.fn();
  const onApprove = vi.fn();
  const onSend = vi.fn();
  const onDiscard = vi.fn();
  render(
    <DraftEditor
      draft={draftValue}
      documents={[]}
      saving={false}
      approving={false}
      sending={false}
      discarding={false}
      error={null}
      onSave={onSave}
      onApprove={onApprove}
      onSend={onSend}
      onDiscard={onDiscard}
      {...overrides}
    />,
  );
  return { onSave, onApprove, onSend, onDiscard };
}

describe('DraftEditor', () => {
  it('user saves only the fields they changed', () => {
    const { onSave } = renderEditor(draft());
    fireEvent.change(screen.getByLabelText('Text'), {
      target: { value: 'Edited body' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledWith({ text: 'Edited body' });
  });

  it('user saves an empty body when nothing changed', () => {
    const { onSave } = renderEditor(draft());
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledWith({});
  });

  it('user sends a first-contact draft', () => {
    const { onSend } = renderEditor(draft());
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(onSend).toHaveBeenCalledOnce();
  });

  it('user approves a letter draft, with recipient and subject locked', () => {
    const { onApprove } = renderEditor(
      draft({ kind: 'customised_letter', recipient: null, subject: null }),
    );
    expect(
      screen.getByRole('button', { name: 'Approve letter as PDF' }),
    ).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Send' })).toBeNull();
    expect(
      (screen.getByLabelText('Recipient') as HTMLInputElement).disabled,
    ).toBe(true);
    fireEvent.click(
      screen.getByRole('button', { name: 'Approve letter as PDF' }),
    );
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it('user sees the grounding warnings', () => {
    renderEditor(
      draft({
        warnings: [
          {
            code: 'placeholder_leftover',
            message: 'Draft mentions an unnamed company.',
          },
        ],
      }),
    );
    expect(screen.getByText('Draft mentions an unnamed company.')).toBeTruthy();
  });

  it('user discards a closed draft even when editing is disabled', () => {
    const { onDiscard } = renderEditor(draft({ status: 'sent' }));
    expect(
      (screen.getByLabelText('Text') as HTMLTextAreaElement).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Discard' }));
    expect(onDiscard).toHaveBeenCalledOnce();
  });

  it('user sees the action error', () => {
    renderEditor(draft(), { error: 'Daily send cap reached.' });
    expect(screen.getByRole('alert').textContent).toContain(
      'Daily send cap reached.',
    );
  });
});
