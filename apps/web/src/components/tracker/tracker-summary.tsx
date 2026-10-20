/** Summary strip above the tracker grid: applications count, the first
 * select column's distribution, and cell completeness. Every number is
 * derived from the live tracker payload — nothing decorative. */

import { DistributionChart } from '@/components/tracker/distribution-chart';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { Distribution } from '@/lib/tracker-stats';

interface TrackerSummaryProps {
  rowCount: number;
  distribution: Distribution;
  fill: { filled: number; total: number };
}

export function TrackerSummary({
  rowCount,
  distribution,
  fill,
}: TrackerSummaryProps) {
  const ratio =
    fill.total === 0 ? 0 : Math.round((fill.filled / fill.total) * 100);

  return (
    <section aria-label="Tracker summary" className="grid gap-4 md:grid-cols-4">
      <Card className="animate-in fade-in slide-in-from-bottom-2 duration-300">
        <CardHeader className="pb-2">
          <CardDescription>Applications</CardDescription>
          <CardTitle className="text-3xl font-semibold tabular-nums">
            {rowCount}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground">
          rows in this tracker
        </CardContent>
      </Card>

      <Card className="animate-in fade-in slide-in-from-bottom-2 delay-75 duration-300 md:col-span-2">
        <CardHeader className="pb-0">
          <CardDescription>
            {distribution.column?.label ?? 'Distribution'}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-2">
          {distribution.column ? (
            <DistributionChart
              label={distribution.column.label}
              entries={distribution.entries}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Add a select column to see its distribution here.
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="animate-in fade-in slide-in-from-bottom-2 delay-150 duration-300">
        <CardHeader className="pb-2">
          <CardDescription>Completeness</CardDescription>
          <CardTitle className="text-3xl font-semibold tabular-nums">
            {ratio}%
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={ratio}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Cells filled"
          >
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${ratio}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {fill.filled} of {fill.total} cells filled
          </p>
        </CardContent>
      </Card>
    </section>
  );
}
