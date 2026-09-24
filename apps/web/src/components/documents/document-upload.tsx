/**
 * Document upload (us-4 items 1, 2): type chosen from the template's list,
 * PDF-only, 3 MB per file. The server sniffs content and enforces the
 * consent gate — a consent_required refusal surfaces as an inline error
 * pointing at the consent screen.
 */

import { useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { DocumentTypeSummary } from '@/lib/tracker-types';

const MAX_UPLOAD_BYTES = 3 * 1024 * 1024;

interface DocumentUploadProps {
  documentTypes: DocumentTypeSummary[];
  uploading: boolean;
  error: string | null;
  onUpload: (file: File, typeKey: string) => void;
}

export function DocumentUpload({
  documentTypes,
  uploading,
  error,
  onUpload,
}: DocumentUploadProps) {
  const [typeKey, setTypeKey] = useState<string>(documentTypes[0]?.key ?? '');
  const [localError, setLocalError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function submit() {
    const file = fileInput.current?.files?.[0];
    if (!file) {
      setLocalError('Choose a file first.');
      return;
    }
    if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
      setLocalError('Only PDF files are accepted.');
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setLocalError('File exceeds the 3 MB limit.');
      return;
    }
    setLocalError(null);
    onUpload(file, typeKey);
  }

  return (
    <section aria-label="Upload a document">
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="upload-type">Document type</FieldLabel>
          <Select
            value={typeKey || undefined}
            onValueChange={(key) => {
              if (key !== null) setTypeKey(key);
            }}
          >
            <SelectTrigger id="upload-type" className="w-full">
              <SelectValue placeholder="—" />
            </SelectTrigger>
            <SelectContent>
              {documentTypes.map((type) => (
                <SelectItem key={type.key} value={type.key}>
                  {type.label}
                  {type.model_eligible ? '' : ' (never sent to the model)'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="upload-file">File (PDF, max 3 MB)</FieldLabel>
          <input
            id="upload-file"
            ref={fileInput}
            type="file"
            accept="application/pdf"
            className="text-xs"
          />
        </Field>
        {localError ? <FieldError>{localError}</FieldError> : null}
        {error ? <FieldError>{error}</FieldError> : null}
        <div>
          <Button type="button" disabled={uploading} onClick={submit}>
            {uploading ? 'Uploading…' : 'Upload'}
          </Button>
        </div>
      </FieldGroup>
    </section>
  );
}
