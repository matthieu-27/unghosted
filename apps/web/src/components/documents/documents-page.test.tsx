import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  project: {} as Record<string, unknown>,
  documents: { isError: false, isPending: false, data: [] },
  profile: {} as Record<string, unknown>,
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => h.project,
}));

const mutation = () => ({ isPending: false, error: null, mutate: () => {} });

vi.mock('@/hooks/use-documents', () => ({
  downloadDocument: () => {},
  useDocuments: () => h.documents,
  useUploadDocument: () => mutation(),
  useDeleteDocument: () => mutation(),
}));

vi.mock('@/hooks/use-consents', () => ({
  useConsents: () => ({ isError: false, isPending: false, data: [] }),
  useGrantConsent: () => mutation(),
  useWithdrawConsent: () => mutation(),
}));

vi.mock('@/hooks/use-profile', () => ({
  useProfileState: () => h.profile,
  useDraftProfile: () => mutation(),
  useEditProfileVersion: () => mutation(),
  useApproveProfileVersion: () => mutation(),
}));

import {
  actionMessage,
  DocumentsPage,
} from '@/components/documents/documents-page';
import { ApiError } from '@/lib/api';

afterEach(cleanup);

beforeEach(() => {
  h.project = {
    isError: false,
    isPending: false,
    data: {
      id: 'p1',
      name: 'Test project',
      document_types: [{ key: 'cv', label: 'CV' }],
    },
  };
  h.documents = { isError: false, isPending: false, data: [] };
  h.profile = {
    isError: false,
    isPending: false,
    data: { approved: null, draft: null, versions: [] },
  };
});

describe('actionMessage', () => {
  it('user sees the mapped sentence for a known consent error code', () => {
    expect(actionMessage(new ApiError(400, 'consent_required', 'detail'))).toBe(
      'Grant model-processing consent first.',
    );
  });

  it('user sees the server detail for an unmapped ApiError code', () => {
    expect(
      actionMessage(new ApiError(400, 'other_code', 'Server detail')),
    ).toBe('Server detail');
  });

  it('user sees the error message for a plain Error', () => {
    expect(actionMessage(new Error('boom'))).toBe('boom');
  });

  it('user sees nothing for a non-error value', () => {
    expect(actionMessage('nope')).toBeNull();
  });
});

describe('DocumentsPage', () => {
  it('user sees an error when a query fails', () => {
    h.project = { isError: true, isPending: false, data: undefined };
    render(<DocumentsPage projectId="p1" />);
    expect(screen.getByText('Cannot load documents page.')).toBeTruthy();
  });

  it('user sees a loading note while queries are pending', () => {
    h.project = { isError: false, isPending: true, data: undefined };
    render(<DocumentsPage projectId="p1" />);
    expect(screen.getByText('Loading…')).toBeTruthy();
  });

  it('user sees the project name once loaded', () => {
    render(<DocumentsPage projectId="p1" />);
    expect(screen.getByText('Documents — Test project')).toBeTruthy();
  });

  it('user sees the error state when the profile query fails', () => {
    h.profile = { isError: true, isPending: false, data: undefined };
    render(<DocumentsPage projectId="p1" />);
    expect(screen.getByText('Cannot load documents page.')).toBeTruthy();
  });
});
