/**
 * Document list (us-4): one row per uploaded file with download and delete.
 * Downloads stream through the API (ownership-checked, decrypted
 * server-side) — no inline rendering from app origin, no presigned URLs.
 */

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { DocumentSummary, DocumentTypeSummary } from '@/lib/tracker-types';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentsTableProps {
  documents: DocumentSummary[];
  documentTypes: DocumentTypeSummary[];
  deleting: boolean;
  error: string | null;
  onDownload: (document: DocumentSummary) => void;
  onDelete: (document: DocumentSummary) => void;
}

export function DocumentsTable({
  documents,
  documentTypes,
  deleting,
  error,
  onDownload,
  onDelete,
}: DocumentsTableProps) {
  if (documents.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No documents yet. Uploaded files appear here.
      </p>
    );
  }
  const labels = new Map(documentTypes.map((t) => [t.key, t.label]));
  return (
    <section aria-label="Uploaded documents">
      {error ? (
        <p role="alert" className="mb-2 text-xs text-red-600">
          {error}
        </p>
      ) : null}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Type</TableHead>
            <TableHead>File</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Eligibility</TableHead>
            <TableHead aria-label="Actions" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => (
            <TableRow key={document.id}>
              <TableCell>
                {labels.get(document.type_key) ?? document.type_key}
              </TableCell>
              <TableCell>{document.original_filename}</TableCell>
              <TableCell>{formatSize(document.size_bytes)}</TableCell>
              <TableCell>
                {document.model_eligible ? (
                  <Badge>Sent to model</Badge>
                ) : (
                  <Badge variant="outline">Never sent to model</Badge>
                )}
              </TableCell>
              <TableCell>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onDownload(document)}
                  >
                    Download
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={deleting}
                    onClick={() => onDelete(document)}
                  >
                    Delete
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
