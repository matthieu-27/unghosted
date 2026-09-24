/** Attachment picker (us-5 item 4): CV and letter documents, visible and
 * removable before sending. */

import { Checkbox } from '@/components/ui/checkbox';
import type { DocumentSummary } from '@/lib/tracker-types';

const DOCUMENT_LABELS: Record<string, string> = {
  cv: 'CV',
  motivation_letter: 'Motivation letter',
  generated_customised_letter: 'Customised letter',
};

interface AttachmentsPickerProps {
  documents: DocumentSummary[];
  selectedIds: string[];
  onChange: (documentIds: string[]) => void;
}

export function AttachmentsPicker({
  documents,
  selectedIds,
  onChange,
}: AttachmentsPickerProps) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No documents to attach. Upload a CV on the documents page first.
      </p>
    );
  }
  return (
    <fieldset className="space-y-1">
      <legend className="text-sm font-medium">Attachments</legend>
      {documents.map((document) => {
        const checked = selectedIds.includes(document.id);
        const checkboxId = `attach-${document.id}`;
        return (
          <label
            key={document.id}
            htmlFor={checkboxId}
            className="flex items-center gap-2 text-sm"
          >
            <Checkbox
              id={checkboxId}
              checked={checked}
              onCheckedChange={(next) => {
                if (next === true) {
                  onChange([...selectedIds, document.id]);
                } else {
                  onChange(selectedIds.filter((id) => id !== document.id));
                }
              }}
              aria-label={`Attach ${document.original_filename}`}
            />
            {document.original_filename} (
            {DOCUMENT_LABELS[document.type_key] ?? document.type_key})
          </label>
        );
      })}
    </fieldset>
  );
}
