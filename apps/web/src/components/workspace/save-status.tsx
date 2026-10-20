/** Save status indicator (user stories, section 3, item 1): a dot that
 * carries the state's colour, text that carries its name. */

import type { SaveStatus } from '@/hooks/use-autosave';

const LABELS: Record<SaveStatus, string> = {
  saved: 'Saved',
  saving: 'Saving…',
  error: 'Offline / error',
  conflict: 'Reloaded after conflict',
  offline: 'Offline / error',
};

const DOT_CLASSES: Record<SaveStatus, string> = {
  saved: 'bg-primary',
  saving: 'animate-pulse bg-muted-foreground',
  error: 'bg-destructive',
  conflict: 'bg-secondary',
  offline: 'bg-destructive',
};

export function SaveStatusIndicator({ status }: { status: SaveStatus }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground"
      role="status"
      aria-live="polite"
      data-status={status}
    >
      <span
        aria-hidden="true"
        className={`size-1.5 rounded-full transition-colors ${DOT_CLASSES[status]}`}
      />
      {LABELS[status]}
    </span>
  );
}
