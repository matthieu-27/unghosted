/**
 * Documents page body (us-4): consent screen, upload, list, applicant
 * profile. The route file keeps the router wiring and passes projectId.
 */

import { useQuery } from '@tanstack/react-query';

import { ConsentScreen } from '@/components/consents/consent-screen';
import { DocumentUpload } from '@/components/documents/document-upload';
import { DocumentsTable } from '@/components/documents/documents-table';
import { ProfileEditor } from '@/components/profile/profile-editor';
import {
  useConsents,
  useGrantConsent,
  useWithdrawConsent,
} from '@/hooks/use-consents';
import {
  downloadDocument,
  useDeleteDocument,
  useDocuments,
  useUploadDocument,
} from '@/hooks/use-documents';
import {
  useApproveProfileVersion,
  useDraftProfile,
  useEditProfileVersion,
  useProfileState,
} from '@/hooks/use-profile';
import { ApiError, apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type {
  ConsentSummary,
  ProfileState,
  ProjectSummary,
} from '@/lib/tracker-types';

const MODEL_CONSENT_ERROR_MESSAGES: Record<string, string> = {
  consent_required: 'Grant model-processing consent first.',
  no_eligible_documents: 'Upload an eligible document first.',
  model_unavailable: 'The model provider is unavailable. Try again later.',
};

const EMPTY_PROFILE: ProfileState = {
  approved: null,
  draft: null,
  versions: [],
};

/** Maps an API error code to the user-facing sentence; other errors keep
 * the server detail. */
export function actionMessage(error: unknown): string | null {
  if (error instanceof ApiError) return apiActionMessage(error);
  if (error instanceof Error) return error.message;
  return null;
}

function apiActionMessage(error: ApiError): string | null {
  return (
    MODEL_CONSENT_ERROR_MESSAGES[error.code ?? ''] ?? error.message ?? null
  );
}

/** True when the user holds a live model-processing consent. */
function hasModelConsent(consentList: ConsentSummary[] | undefined): boolean {
  return (
    consentList?.some(
      (c) => c.kind === 'model_processing' && c.withdrawn_at === null,
    ) ?? false
  );
}

function hasFailed(queries: { isError: boolean }[]): boolean {
  return queries.some((query) => query.isError);
}

function isLoading(queries: { isPending: boolean }[]): boolean {
  return queries.some((query) => query.isPending);
}

/** First mutation error among the given mutations, or null. */
function firstMutationError(mutations: { error: unknown }[]): unknown {
  for (const mutation of mutations) {
    if (mutation.error) return mutation.error;
  }
  return null;
}

/** All queries, mutations, and derived view state for the documents page. */
function useDocumentsPage(projectId: string) {
  const project = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => apiFetch<ProjectSummary>(`/projects/${projectId}`),
  });
  const documents = useDocuments(projectId);
  const consents = useConsents();
  const profile = useProfileState(projectId);

  const upload = useUploadDocument(projectId);
  const deleteDocument = useDeleteDocument(projectId);
  const grantConsent = useGrantConsent();
  const withdrawConsent = useWithdrawConsent();
  const draft = useDraftProfile(projectId);
  const edit = useEditProfileVersion(projectId);
  const approve = useApproveProfileVersion(projectId);

  return {
    failed: hasFailed([project, documents, profile]),
    loading: isLoading([project, documents]),
    projectName: project.data?.name ?? '…',
    documentTypes: project.data?.document_types ?? [],
    documents: documents.data ?? [],
    consentGranted: hasModelConsent(consents.data),
    profile: profile.data ?? EMPTY_PROFILE,
    consentError: actionMessage(
      firstMutationError([grantConsent, withdrawConsent]),
    ),
    uploadError: actionMessage(upload.error),
    deleteError: actionMessage(deleteDocument.error),
    profileError: actionMessage(firstMutationError([draft, edit, approve])),
    actions: {
      upload,
      deleteDocument,
      grantConsent,
      withdrawConsent,
      draft,
      edit,
      approve,
    },
  };
}

export function DocumentsPage({ projectId }: { projectId: string }) {
  const page = useDocumentsPage(projectId);
  const {
    projectName,
    documentTypes,
    documents,
    consentGranted,
    profile,
    consentError,
    uploadError,
    deleteError,
    profileError,
    actions,
  } = page;

  if (page.failed) {
    return (
      <main className="container mx-auto p-8">
        <p role="alert" className="text-sm text-red-600">
          Cannot load documents page.
        </p>
      </main>
    );
  }
  if (page.loading) {
    return (
      <main className="container mx-auto p-8">
        <p>Loading…</p>
      </main>
    );
  }

  return (
    <main className="container mx-auto space-y-6 p-8">
      <h1 className="text-lg font-medium">Documents — {projectName}</h1>

      <ConsentScreen
        granted={consentGranted}
        granting={actions.grantConsent.isPending}
        error={consentError}
        onGrant={() => actions.grantConsent.mutate('model_processing')}
        onWithdraw={() => actions.withdrawConsent.mutate('model_processing')}
      />

      <DocumentUpload
        documentTypes={documentTypes}
        uploading={actions.upload.isPending}
        error={uploadError}
        onUpload={(file, typeKey) => actions.upload.mutate({ file, typeKey })}
      />

      <DocumentsTable
        documents={documents}
        documentTypes={documentTypes}
        deleting={actions.deleteDocument.isPending}
        error={deleteError}
        onDownload={(document) => {
          void downloadDocument(
            projectId,
            document.id,
            document.original_filename,
          );
        }}
        onDelete={(document) => actions.deleteDocument.mutate(document.id)}
      />

      <ProfileEditor
        state={profile}
        drafting={actions.draft.isPending}
        saving={actions.edit.isPending}
        approving={actions.approve.isPending}
        error={profileError}
        onDraft={() => actions.draft.mutate()}
        onSave={(version, body) => actions.edit.mutate({ version, body })}
        onApprove={(version) => actions.approve.mutate(version)}
      />
    </main>
  );
}
