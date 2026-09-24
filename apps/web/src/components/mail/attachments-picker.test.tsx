import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DocumentSummary } from '@/lib/tracker-types';
import { AttachmentsPicker } from './attachments-picker';

afterEach(cleanup);

function document(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: 'd1',
    type_key: 'cv',
    model_eligible: true,
    original_filename: 'cv.pdf',
    size_bytes: 1024,
    created_at: '2026-09-24T09:00:00Z',
    ...overrides,
  };
}

function renderPicker(
  documents: DocumentSummary[],
  selectedIds: string[],
): { onChange: ReturnType<typeof vi.fn> } {
  const onChange = vi.fn();
  render(
    <AttachmentsPicker
      documents={documents}
      selectedIds={selectedIds}
      onChange={onChange}
    />,
  );
  return { onChange };
}

describe('AttachmentsPicker', () => {
  // Base UI wires the checkbox to its wrapping <label> via
  // aria-labelledby, so the accessible name also carries the file name.
  const checkbox = () =>
    screen.getByRole('checkbox', { name: /Attach cv\.pdf/ });

  it('user adds a document to the attachments', () => {
    const { onChange } = renderPicker([document()], []);
    fireEvent.click(checkbox());
    expect(onChange).toHaveBeenCalledWith(['d1']);
  });

  it('user removes a selected document from the attachments', () => {
    const { onChange } = renderPicker([document()], ['d1']);
    fireEvent.click(checkbox());
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('user sees the document type label next to the file name', () => {
    renderPicker([document({ type_key: 'generated_customised_letter' })], []);
    expect(screen.getByText(/cv\.pdf \(Customised letter\)/)).toBeTruthy();
  });

  it('user sees a hint when the project has no documents', () => {
    renderPicker([], []);
    expect(
      screen.getByText(
        'No documents to attach. Upload a CV on the documents page first.',
      ),
    ).toBeTruthy();
  });
});
