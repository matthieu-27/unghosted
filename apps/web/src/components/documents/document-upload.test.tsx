import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { DocumentTypeSummary } from '@/lib/tracker-types';
import { DocumentUpload } from './document-upload';

afterEach(cleanup);

const documentTypes: DocumentTypeSummary[] = [
  { key: 'cv', label: 'CV', model_eligible: true },
  { key: 'id_document', label: 'ID document', model_eligible: false },
];

function renderUpload(
  overrides: Partial<Parameters<typeof DocumentUpload>[0]> = {},
) {
  const onUpload = vi.fn();
  render(
    <DocumentUpload
      documentTypes={documentTypes}
      uploading={false}
      error={null}
      onUpload={onUpload}
      {...overrides}
    />,
  );
  return { onUpload };
}

function pdfFile(name = 'cv.pdf'): File {
  return new File(['%PDF'], name, { type: 'application/pdf' });
}

function pickFile(file: File | null) {
  const input = screen.getByLabelText(/File \(PDF, max 3 MB\)/);
  fireEvent.change(input, { target: { files: file ? [file] : [] } });
}

describe('DocumentUpload', () => {
  it('rejects the upload when no file is chosen', () => {
    const { onUpload } = renderUpload();
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByText('Choose a file first.')).toBeTruthy();
  });

  it('rejects a non-PDF file before any network call', () => {
    const { onUpload } = renderUpload();
    pickFile(new File(['x'], 'cv.txt', { type: 'text/plain' }));
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByText('Only PDF files are accepted.')).toBeTruthy();
  });

  it('rejects a file above the 3 MB limit', () => {
    const { onUpload } = renderUpload();
    const big = new File([new ArrayBuffer(3 * 1024 * 1024 + 1)], 'big.pdf', {
      type: 'application/pdf',
    });
    pickFile(big);
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByText('File exceeds the 3 MB limit.')).toBeTruthy();
  });

  it('uploads the chosen file with the first type by default', () => {
    const { onUpload } = renderUpload();
    const file = pdfFile();
    pickFile(file);
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    expect(onUpload).toHaveBeenCalledWith(file, 'cv');
  });

  it('shows the server refusal and disables the button while uploading', () => {
    renderUpload({
      uploading: true,
      error: 'Grant model-processing consent first.',
    });
    expect(
      screen
        .getByRole('button', { name: 'Uploading…' })
        .hasAttribute('disabled'),
    ).toBe(true);
    expect(
      screen.getByText('Grant model-processing consent first.'),
    ).toBeTruthy();
  });
});
