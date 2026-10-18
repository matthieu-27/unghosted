/** Save status indicator (user stories, section 3, item 1). */

import type { SaveStatus } from '@/hooks/use-autosave';

const LABELS: Record<SaveStatus, string> = {
  saved: 'Saved',
  saving: 'Saving…',
  error: 'Offline / error',
  conflict: 'Reloaded after conflict',
  offline: 'Offline / error',
};

export function SaveStatusIndicator({ status }: { status: SaveStatus }) {
  return (
    <span
      className="text-sm text-muted-foreground"
      role="status"
      aria-live="polite"
      data-status={status}
    >
      {LABELS[status]}
    </span>
  );
}
