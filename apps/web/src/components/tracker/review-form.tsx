/**
 * Review form for "+ New application" (us-3, item 5): pre-filled fields with
 * provenance chips, duplicate and mismatch warnings, editable page kind,
 * nothing saved until the user confirms.
 */

import { useMemo, useState } from 'react';

import { OptionSelect } from '@/components/tracker/option-select';
import { Button } from '@/components/ui/button';
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  type AnalysisWarning,
  type ColumnDefinition,
  type LinkAnalysisResult,
  PAGE_KIND_LABELS,
} from '@/lib/tracker-types';

const PROVENANCE_LABELS: Record<string, string> = {
  structured: 'structured data',
  meta: 'page meta',
  model: 'model',
  detection: 'detection',
  manual: 'manual',
};

const NUMERIC_TYPES: ReadonlySet<string> = new Set([
  'number',
  'currency',
  'percent',
  'rating',
]);

export interface ReviewValues {
  kind: string;
  cells: Record<string, unknown>;
}

/** Human label for a provenance chip, or undefined when data was hand-entered. */
function provenanceChipLabel(
  provenance: Map<string, string>,
  columnKey: string,
): string | undefined {
  const raw = provenance.get(columnKey);
  if (raw === undefined) return undefined;
  return PROVENANCE_LABELS[raw] ?? raw;
}

/** Columns the user may edit: no system columns, no computed columns. */
function editableColumns(columns: ColumnDefinition[]): ColumnDefinition[] {
  return columns.filter((column) => !column.system && !column.computed);
}

const inputTypeFor = (column: ColumnDefinition): string => {
  if (column.type === 'date') return 'date';
  return NUMERIC_TYPES.has(column.type) ? 'number' : 'text';
};

interface ColumnReviewInputProps {
  column: ColumnDefinition;
  value: string;
  onChange: (value: string) => void;
}

/** The type-appropriate input for one editable column. */
function ColumnReviewInput({
  column,
  value,
  onChange,
}: ColumnReviewInputProps) {
  if (column.type === 'long-text') {
    return (
      <Textarea
        id={`review-${column.key}`}
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (column.type === 'select') {
    return (
      <OptionSelect
        column={column}
        value={value || undefined}
        onValueChange={(key) => {
          if (key !== null) onChange(key);
        }}
        triggerId={`review-${column.key}`}
        triggerClassName="w-full"
      />
    );
  }
  return (
    <Input
      id={`review-${column.key}`}
      type={inputTypeFor(column)}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

interface ColumnReviewFieldProps {
  column: ColumnDefinition;
  value: string;
  provenanceLabel: string | undefined;
  onChange: (value: string) => void;
}

/** One editable column: label + provenance chip + type-appropriate input. */
function ColumnReviewField({
  column,
  value,
  provenanceLabel,
  onChange,
}: ColumnReviewFieldProps) {
  return (
    <Field>
      <FieldLabel htmlFor={`review-${column.key}`}>
        {column.label}
        {provenanceLabel ? (
          <span className="ml-2 rounded-sm bg-muted px-1 font-mono text-[10px] uppercase tracking-wide">
            {provenanceLabel}
          </span>
        ) : null}
      </FieldLabel>
      <ColumnReviewInput column={column} value={value} onChange={onChange} />
    </Field>
  );
}

/** Duplicate and mismatch warnings from the analysis, if any. */
function WarningsList({ warnings }: { warnings: AnalysisWarning[] }) {
  if (warnings.length === 0) return null;
  return (
    <div role="alert" className="mb-3 rounded-md border border-amber-500 p-2">
      <ul className="list-disc pl-4 text-sm">
        {warnings.map((w) => (
          <li key={w.code}>{w.detail}</li>
        ))}
      </ul>
    </div>
  );
}

/** How the page kind was detected, shown under the kind selector. */
function PageKindMeta({ result }: { result: LinkAnalysisResult }) {
  if (!result.page_kind_confidence) return null;
  return (
    <p className="text-xs text-muted-foreground">
      detected via {result.page_kind_basis} ({result.page_kind_confidence}
      {result.provider ? `, filled by ${result.provider}` : ''}
      {result.cached ? ', from cache' : ''})
    </p>
  );
}

function initialValue(
  column: ColumnDefinition,
  extracted: Map<string, unknown>,
): string {
  const value = extracted.get(column.key);
  if (value == null) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

/** One cell as the tracker expects it, or null when the field was left empty. */
function coercedCell(
  column: ColumnDefinition,
  raw: string,
): [string, unknown] | null {
  if (raw === '') return null;
  const value = NUMERIC_TYPES.has(column.type)
    ? Number(raw)
    : column.type === 'checkbox'
      ? raw === 'true'
      : raw;
  return [column.key, value];
}

/** All non-empty editable fields, coerced to their column types. */
function reviewCells(
  columns: ColumnDefinition[],
  values: Record<string, string>,
): Record<string, unknown> {
  const cells: Record<string, unknown> = {};
  for (const column of columns) {
    const coerced = coercedCell(column, values[column.key] ?? '');
    if (coerced) cells[coerced[0]] = coerced[1];
  }
  return cells;
}

interface SaveButtonsProps {
  saving: boolean;
  onCancel: () => void;
  onCommit: () => void;
}

/** Cancel/Save pair; Save is disabled and relabelled while saving. */
function SaveButtons({ saving, onCancel, onCommit }: SaveButtonsProps) {
  return (
    <div className="flex justify-end gap-2">
      <Button type="button" variant="outline" onClick={onCancel}>
        Cancel
      </Button>
      <Button type="button" disabled={saving} onClick={onCommit}>
        {saving ? 'Saving…' : 'Save row'}
      </Button>
    </div>
  );
}

interface ReviewFormProps {
  columns: ColumnDefinition[];
  result: LinkAnalysisResult;
  saving: boolean;
  error: string | null;
  onKindChange: (kind: string) => void;
  onSave: (values: ReviewValues) => void;
  onCancel: () => void;
}

export function ReviewForm({
  columns,
  result,
  saving,
  error,
  onKindChange,
  onSave,
  onCancel,
}: ReviewFormProps) {
  const extracted = useMemo(
    () => new Map(result.fields.map((f) => [f.column_key, f.value])),
    [result.fields],
  );
  const provenance = useMemo(
    () => new Map(result.fields.map((f) => [f.column_key, f.provenance])),
    [result.fields],
  );
  const editable = useMemo(() => editableColumns(columns), [columns]);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      editable.map((c) => [c.key, initialValue(c, extracted)]),
    ),
  );

  function commit() {
    onSave({
      kind: result.page_kind ?? 'other',
      cells: reviewCells(editable, values),
    });
  }

  return (
    <section aria-label="Review the pre-filled application">
      <WarningsList warnings={result.warnings} />

      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="review-kind">Page kind</FieldLabel>
          <Select
            value={result.page_kind ?? undefined}
            onValueChange={(kind) => {
              if (kind !== null) onKindChange(kind);
            }}
          >
            <SelectTrigger id="review-kind" className="w-full">
              <SelectValue placeholder="—" />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(PAGE_KIND_LABELS).map(([key, label]) => (
                <SelectItem key={key} value={key}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <PageKindMeta result={result} />
        </Field>

        {editable.map((column) => (
          <ColumnReviewField
            key={column.key}
            column={column}
            value={values[column.key] ?? ''}
            provenanceLabel={provenanceChipLabel(provenance, column.key)}
            onChange={(value) =>
              setValues((v) => ({ ...v, [column.key]: value }))
            }
          />
        ))}

        {error ? <FieldError>{error}</FieldError> : null}

        <SaveButtons saving={saving} onCancel={onCancel} onCommit={commit} />
      </FieldGroup>
    </section>
  );
}
