/**
 * Autosave: batches tracker operations, applies them optimistically, flushes
 * after a debounce, and handles stale revisions by refetching once and
 * replaying still-relevant cell edits (the minimal M1 rebase).
 */

import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { applyLocal } from '@/lib/tracker-local';
import type { TrackerOperation, TrackerRow } from '@/lib/tracker-types';

export type SaveStatus = 'saved' | 'saving' | 'error' | 'conflict' | 'offline';

const FLUSH_DEBOUNCE_MS = 800;

export function useAutosave(
  projectId: string,
  serverRows: TrackerRow[] | undefined,
  serverRevision: number | undefined,
) {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<TrackerRow[]>([]);
  const [status, setStatus] = useState<SaveStatus>('saved');
  const pending = useRef<TrackerOperation[]>([]);
  const baseRevision = useRef<number>(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushing = useRef(false);

  const flush = useCallback(async () => {
    if (flushing.current || pending.current.length === 0) return;
    flushing.current = true;
    const sent = [...pending.current];
    setStatus('saving');
    try {
      await apiFetch(`/projects/${projectId}/tracker/operations`, {
        method: 'PATCH',
        body: JSON.stringify({
          base_revision: baseRevision.current,
          operations: sent,
        }),
      });
      pending.current = pending.current.filter((op) => !sent.includes(op));
      await queryClient.invalidateQueries({
        queryKey: queryKeys.tracker(projectId),
      });
      if (pending.current.length === 0) setStatus('saved');
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        // Minimal rebase: take the server's current state, replay pending
        // cell edits once. Row ops are dropped (their ids changed).
        pending.current = pending.current.filter((op) => op.op === 'set_cell');
        await queryClient.invalidateQueries({
          queryKey: queryKeys.tracker(projectId),
        });
        setStatus('conflict');
      } else {
        setStatus('error');
      }
    } finally {
      flushing.current = false;
      if (pending.current.length > 0) {
        timer.current = setTimeout(() => void flush(), FLUSH_DEBOUNCE_MS);
      }
    }
  }, [projectId, queryClient]);

  const push = useCallback(
    (operation: TrackerOperation) => {
      pending.current = [...pending.current, operation];
      setRows((current) => applyLocal(current, operation));
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void flush(), FLUSH_DEBOUNCE_MS);
    },
    [flush],
  );

  // Server data wins whenever there are no pending edits (initial load,
  // post-flush refetch, window-focus refetch).
  useEffect(() => {
    if (pending.current.length === 0 && serverRows) {
      setRows(serverRows);
      if (serverRevision !== undefined) {
        baseRevision.current = serverRevision;
      }
      setStatus('saved');
    }
  }, [serverRows, serverRevision]);

  // Stop the debounce timer on unmount.
  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  return useMemo(() => ({ rows, status, push }), [rows, status, push]);
}
