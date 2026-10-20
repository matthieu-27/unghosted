/** Loading placeholder for the tracker page: the summary strip and the
 * grid block, same shapes as the real page so the load does not jump. */

import { Skeleton } from '@/components/ui/skeleton';

export function TrackerSkeleton() {
  return (
    <div
      className="flex flex-col gap-4"
      role="status"
      aria-busy="true"
      aria-label="Loading tracker"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-36 rounded-xl" />
        <Skeleton className="h-36 rounded-xl md:col-span-2" />
        <Skeleton className="h-36 rounded-xl" />
      </div>
      <Skeleton className="h-9 w-full max-w-md rounded-md" />
      <Skeleton className="h-[60vh] rounded-xl" />
    </div>
  );
}
