/**
 * "+ New application" modal (us-3): one paste (URL or text, auto-detected),
 * then the review form. Saving inserts a row and sets cells through the
 * operations endpoint: two batches, because the server assigns the row id
 * on insert_rows.
 */

import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  ReviewForm,
  type ReviewValues,
} from '@/components/tracker/review-form';
import { Button } from '@/components/ui/button';
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { useLinkAnalysis } from '@/hooks/use-link-analysis';
import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type {
  ColumnDefinition,
  LinkAnalysisResult,
  TrackerPayload,
} from '@/lib/tracker-types';

interface NewApplicationModalProps {
  open: boolean;
  projectId: string;
  columns: ColumnDefinition[];
  revision: number;
  onClose: () => void;
}

function detectInputKind(raw: string): 'url' | 'text' {
  const trimmed = raw.trim();
  if (!/\s/.test(trimmed) && /^https?:\/\/\S+$/.test(trimmed)) return 'url';
  return 'text';
}

/** URL/text detection, or null while the paste field is empty. */
function detectPasteKind(raw: string): 'url' | 'text' | null {
  if (raw.trim() === '') return null;
  return detectInputKind(raw);
}

function inputKindHint(kind: 'url' | 'text' | null): string {
  if (kind === 'url') return 'Detected: URL';
  if (kind === 'text') return 'Detected: text';
  return 'One paste: link or text, we detect which.';
}

interface PasteFormProps {
  input: string;
  inputKind: 'url' | 'text' | null;
  pending: boolean;
  error: string | null;
  onInputChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

/** The single paste field plus its URL/text detection hint. */
function PasteForm({
  input,
  inputKind,
  pending,
  error,
  onInputChange,
  onSubmit,
  onCancel,
}: PasteFormProps) {
  return (
    <form
      className="mt-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="new-application-input">
            Paste a listing URL or text
          </FieldLabel>
          <Input
            id="new-application-input"
            value={input}
            placeholder="https://… or paste the listing text"
            aria-describedby="new-application-kind"
            onChange={(e) => onInputChange(e.target.value)}
          />
          <p
            id="new-application-kind"
            className="text-xs text-muted-foreground"
          >
            {inputKindHint(inputKind)}
          </p>
        </Field>
        {error ? <FieldError>{error}</FieldError> : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? 'Analyzing…' : 'Analyze'}
          </Button>
        </div>
      </FieldGroup>
    </form>
  );
}

/** set_cell operations for the values a ReviewForm collected. */
function cellOperations(
  rowId: string,
  cells: Record<string, unknown>,
): { op: 'set_cell'; row_id: string; column_key: string; value: unknown }[] {
  return Object.entries(cells).map(([column_key, value]) => ({
    op: 'set_cell' as const,
    row_id: rowId,
    column_key,
    value,
  }));
}

export function NewApplicationModal({
  open,
  projectId,
  columns,
  revision,
  onClose,
}: NewApplicationModalProps) {
  const queryClient = useQueryClient();
  const [input, setInput] = useState('');
  const [review, setReview] = useState<LinkAnalysisResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const analysis = useLinkAnalysis(projectId);

  if (!open) return null;

  const inputKind = detectPasteKind(input);
  const pasteError = analysis.isError ? String(analysis.error) : saveError;

  async function runAnalysis(forceKind: string | null = null) {
    setSaveError(null);
    try {
      const result = await analysis.mutateAsync({
        input,
        force_kind: forceKind,
      });
      setReview(result);
    } catch {
      // apiFetch errors already carry detail; surface generically here.
      setSaveError('Analysis failed. Check the API and try again.');
    }
  }

  async function save(values: ReviewValues) {
    setSaving(true);
    setSaveError(null);
    try {
      const trackerKey = queryKeys.tracker(projectId);
      const inserted = await apiFetch<{ revision: number }>(
        `/projects/${projectId}/tracker/operations`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            base_revision: revision,
            operations: [{ op: 'insert_rows', count: 1 }],
          }),
        },
      );
      const payload = await queryClient.fetchQuery({
        queryKey: trackerKey,
        queryFn: () =>
          apiFetch<TrackerPayload>(`/projects/${projectId}/tracker`),
        staleTime: 0,
      });
      // insert_rows without after_row_id appends: the new row is last.
      const lastRow = payload.rows[payload.rows.length - 1];
      if (!lastRow) throw new Error('inserted row not found after refetch');
      await apiFetch(`/projects/${projectId}/tracker/operations`, {
        method: 'PATCH',
        body: JSON.stringify({
          base_revision: inserted.revision,
          operations: cellOperations(lastRow.id, values.cells),
        }),
      });
      await queryClient.invalidateQueries({ queryKey: trackerKey });
      reset();
    } catch (error) {
      setSaveError(String(error));
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setInput('');
    setReview(null);
    setSaveError(null);
    analysis.reset();
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="New application"
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg bg-background p-6 shadow-xl"
      >
        <h2 className="text-lg font-semibold">New application</h2>
        {review ? (
          <div className="mt-4">
            <ReviewForm
              columns={columns}
              result={review}
              saving={saving}
              error={saveError}
              onKindChange={(kind) => {
                void runAnalysis(kind);
              }}
              onSave={(values) => {
                void save(values);
              }}
              onCancel={reset}
            />
          </div>
        ) : (
          <PasteForm
            input={input}
            inputKind={inputKind}
            pending={analysis.isPending}
            error={pasteError}
            onInputChange={setInput}
            onSubmit={() => {
              void runAnalysis();
            }}
            onCancel={reset}
          />
        )}
      </div>
    </div>
  );
}
