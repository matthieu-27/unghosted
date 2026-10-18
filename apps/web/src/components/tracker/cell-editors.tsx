/**
 * Type-appropriate cell editors and display, one per column type
 * (user stories, section 3, item 1), on shadcn primitives (Base UI).
 * Contact/document-link editors land with their features (post-MVP).
 */

import { OptionSelect } from '@/components/tracker/option-select';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import type { ColumnDefinition, TrackerRow } from '@/lib/tracker-types';

export function CellDisplay({
  column,
  row,
}: {
  column: ColumnDefinition;
  row: TrackerRow;
}) {
  const value = row.cells[column.key];
  if (value == null || value === '')
    return <span className="text-muted-foreground">—</span>;
  if (column.type === 'checkbox') {
    return (
      <span role="img" aria-label={value ? 'checked' : 'unchecked'}>
        {value ? '☑' : '☐'}
      </span>
    );
  }
  if (column.type === 'rating') {
    return (
      <span role="img" aria-label={`${value} of ${column.max ?? 5}`}>
        {'★'.repeat(Number(value))}
        {'☆'.repeat((column.max ?? 5) - Number(value))}
      </span>
    );
  }
  if (column.type === 'select') {
    const option = column.options?.find((o) => o.key === value);
    return <span>{option?.label ?? String(value)}</span>;
  }
  return <span>{String(value)}</span>;
}

interface EditorProps {
  column: ColumnDefinition;
  row: TrackerRow;
  onCommit: (value: unknown) => void;
  onCancel: () => void;
}

export function CellEditor({ column, row, onCommit, onCancel }: EditorProps) {
  const initial = row.cells[column.key];

  switch (column.type) {
    case 'long-text':
      return (
        <Textarea
          autoFocus
          aria-label={column.label}
          defaultValue={typeof initial === 'string' ? initial : ''}
          rows={3}
          onFocus={(e) => e.target.select()}
          onBlur={(e) => onCommit(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onCancel();
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              onCommit((e.target as HTMLTextAreaElement).value);
            }
          }}
        />
      );
    case 'select':
      return (
        <OptionSelect
          column={column}
          open
          onOpenChange={(open) => {
            if (!open) onCancel();
          }}
          value={typeof initial === 'string' ? initial : undefined}
          onValueChange={(value) => onCommit(value)}
          autoFocus
        />
      );
    case 'checkbox':
      return (
        <Checkbox
          autoFocus
          checked={initial === true}
          onCheckedChange={(checked) => onCommit(checked)}
          onBlur={() => onCancel()}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onCancel();
          }}
        />
      );
    case 'rating':
      return (
        <RadioGroup
          value={initial == null ? undefined : String(initial)}
          onValueChange={(value) => onCommit(Number(value))}
          className="flex gap-0.5"
          aria-label={column.label}
        >
          {Array.from({ length: column.max ?? 5 }, (_, i) => i + 1).map((n) => (
            <div key={n} className="flex cursor-pointer items-center">
              <RadioGroupItem
                id={`rating-${column.key}-${n}`}
                value={String(n)}
                className="sr-only"
              />
              <label htmlFor={`rating-${column.key}-${n}`}>
                <span aria-hidden="true">
                  {Number(initial) >= n ? '★' : '☆'}
                </span>
                <span className="sr-only">{`${n} of ${column.max ?? 5}`}</span>
              </label>
            </div>
          ))}
        </RadioGroup>
      );
    case 'number':
    case 'currency':
    case 'percent':
      return (
        <Input
          autoFocus
          aria-label={column.label}
          type="number"
          step="any"
          defaultValue={typeof initial === 'number' ? initial : ''}
          onFocus={(e) => e.target.select()}
          onBlur={(e) =>
            onCommit(e.target.value === '' ? null : Number(e.target.value))
          }
          onKeyDown={(e) => {
            if (e.key === 'Enter')
              onCommit((e.target as HTMLInputElement).value);
            if (e.key === 'Escape') onCancel();
          }}
        />
      );
    case 'date':
      return (
        <Input
          autoFocus
          aria-label={column.label}
          type="date"
          defaultValue={typeof initial === 'string' ? initial : ''}
          onBlur={(e) => onCommit(e.target.value || null)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onCancel();
          }}
        />
      );
    default:
      // text, url, email, phone
      return (
        <Input
          autoFocus
          aria-label={column.label}
          type="text"
          defaultValue={typeof initial === 'string' ? initial : ''}
          onFocus={(e) => e.target.select()}
          onBlur={(e) => onCommit(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter')
              onCommit((e.target as HTMLInputElement).value);
            if (e.key === 'Escape') onCancel();
          }}
        />
      );
  }
}
