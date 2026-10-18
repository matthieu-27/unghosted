import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DocumentSummary, DocumentTypeSummary } from '@/lib/tracker-types';
import { DocumentsTable } from './documents-table';

afterEach(cleanup);

const documentTypes: DocumentTypeSummary[] = [
  { key: 'cv', label: 'CV', model_eligible: true },
  { key: 'id_document', label: 'ID document', model_eligible: false },
];

const documents: DocumentSummary[] = [
  {
    id: 'd1',
    type_key: 'cv',
    model_eligible: true,
    original_filename: 'cv.pdf',
    size_bytes: 2048,
    created_at: '2026-09-23T09:00:00Z',
  },
  {
    id: 'd2',
    type_key: 'id_document',
    model_eligible: false,
    original_filename: 'id.pdf',
    size_bytes: 5 * 1024 * 1024,
    created_at: '2026-09-23T09:01:00Z',
  },
];

function renderTable(
  overrides: Partial<Parameters<typeof DocumentsTable>[0]> = {},
) {
  const onDownload = vi.fn();
  const onDelete = vi.fn();
  render(
    <DocumentsTable
      documents={documents}
      documentTypes={documentTypes}
      deleting={false}
      error={null}
      onDownload={onDownload}
      onDelete={onDelete}
      {...overrides}
    />,
  );
  return { onDownload, onDelete };
}

describe('DocumentsTable', () => {
  it('lists each document with its type label, size and eligibility badge', () => {
    renderTable();
    expect(screen.getByText('CV')).toBeTruthy();
    expect(screen.getByText('ID document')).toBeTruthy();
    expect(screen.getByText('cv.pdf')).toBeTruthy();
    expect(screen.getByText('2.0 kB')).toBeTruthy();
    expect(screen.getByText('5.0 MB')).toBeTruthy();
    expect(screen.getByText('Sent to model')).toBeTruthy();
    expect(screen.getByText('Never sent to model')).toBeTruthy();
  });

  it('downloads the document whose download button is clicked', () => {
    const { onDownload } = renderTable();
    const [first] = screen.getAllByRole('button', { name: 'Download' });
    if (first === undefined) throw new Error('no download button rendered');
    fireEvent.click(first);
    expect(onDownload).toHaveBeenCalledWith(documents[0]);
  });

  it('deletes the document whose delete button is clicked', () => {
    const { onDelete } = renderTable();
    const second = screen.getAllByRole('button', { name: 'Delete' })[1];
    if (second === undefined) throw new Error('no second delete button');
    fireEvent.click(second);
    expect(onDelete).toHaveBeenCalledWith(documents[1]);
  });

  it('shows the empty state when there are no documents', () => {
    render(
      <DocumentsTable
        documents={[]}
        documentTypes={documentTypes}
        deleting={false}
        error={null}
        onDownload={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(
      screen.getByText('No documents yet. Uploaded files appear here.'),
    ).toBeTruthy();
  });

  it('shows the action error', () => {
    renderTable({ error: 'Delete failed.' });
    expect(screen.getByRole('alert').textContent).toContain('Delete failed.');
  });
});
