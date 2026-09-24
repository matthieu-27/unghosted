import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ProfileState, ProfileVersion } from '@/lib/tracker-types';
import { ProfileEditor } from './profile-editor';

afterEach(cleanup);

function version(overrides: Partial<ProfileVersion> = {}): ProfileVersion {
  return {
    version: 1,
    status: 'draft',
    headline: 'Curious data apprentice',
    seeking: 'A work-study data role',
    highlights: [{ id: 'h1', text: 'Built a tracker' }],
    motivation: 'Wants to learn',
    style_notes: [{ id: 's1', text: 'Direct tone' }],
    availability: 'From September',
    approved_at: null,
    created_at: '2026-09-23T09:00:00Z',
    updated_at: '2026-09-23T09:00:00Z',
    ...overrides,
  };
}

function renderEditor(
  state: ProfileState,
  overrides: Partial<Parameters<typeof ProfileEditor>[0]> = {},
) {
  const onDraft = vi.fn();
  const onSave = vi.fn();
  const onApprove = vi.fn();
  render(
    <ProfileEditor
      state={state}
      drafting={false}
      saving={false}
      approving={false}
      error={null}
      onDraft={onDraft}
      onSave={onSave}
      onApprove={onApprove}
      {...overrides}
    />,
  );
  return { onDraft, onSave, onApprove };
}

describe('ProfileEditor', () => {
  it('offers draft generation when there is no draft yet', () => {
    const { onDraft } = renderEditor({
      approved: null,
      draft: null,
      versions: [],
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Generate draft from documents' }),
    );
    expect(onDraft).toHaveBeenCalledOnce();
  });

  it('shows the approved version read-only next to the draft', () => {
    const approved = version({
      version: 1,
      status: 'approved',
      approved_at: '2026-09-23T10:00:00Z',
    });
    const draft = version({ version: 2 });
    renderEditor({ approved, draft, versions: [approved, draft] });
    expect(screen.getByText('Approved (version 1)')).toBeTruthy();
    expect(screen.getByText('Draft (version 2)')).toBeTruthy();
  });

  it('saves the edited headline along with the untouched fields', () => {
    const { onSave } = renderEditor({
      approved: null,
      draft: version(),
      versions: [version()],
    });
    fireEvent.change(screen.getByLabelText('Headline'), {
      target: { value: 'Hand-tuned headline' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    expect(onSave).toHaveBeenCalledWith(1, {
      headline: 'Hand-tuned headline',
      seeking: 'A work-study data role',
      motivation: 'Wants to learn',
      availability: 'From September',
      highlights: [{ id: 'h1', text: 'Built a tracker' }],
      style_notes: [{ id: 's1', text: 'Direct tone' }],
    });
  });

  it('omits a field the user cleared, so the stored value survives', () => {
    const { onSave } = renderEditor({
      approved: null,
      draft: version(),
      versions: [version()],
    });
    fireEvent.change(screen.getByLabelText('Seeking'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    const body = onSave.mock.calls[0]?.[1];
    expect(body).toBeDefined();
    expect('seeking' in (body as object)).toBe(false);
  });

  it('approves the current draft version', () => {
    const { onApprove } = renderEditor({
      approved: null,
      draft: version(),
      versions: [version()],
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Approve this version' }),
    );
    expect(onApprove).toHaveBeenCalledWith(1);
  });

  it('shows the draft action error', () => {
    renderEditor(
      { approved: null, draft: null, versions: [] },
      { error: 'Upload an eligible document first.' },
    );
    expect(screen.getByRole('alert').textContent).toContain(
      'Upload an eligible document first.',
    );
  });
});
