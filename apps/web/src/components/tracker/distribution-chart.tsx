/** Distribution chart: horizontal bars of the first select column's option
 * counts, one bar per option in the template's own colour when it has one.
 * Pure presentation — the counts come from tracker-stats (tested there). */

import { Bar, BarChart, Cell, LabelList, XAxis, YAxis } from 'recharts';

import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import type { DistributionEntry } from '@/lib/tracker-stats';

interface DistributionChartProps {
  label: string;
  entries: DistributionEntry[];
}

export function DistributionChart({ label, entries }: DistributionChartProps) {
  const config = {
    count: { label },
  } satisfies ChartConfig;
  const total = entries.reduce((sum, entry) => sum + entry.count, 0);

  return (
    <ChartContainer config={config} className="h-[152px] w-full">
      <BarChart
        data={entries}
        layout="vertical"
        margin={{ left: 0, right: 16, top: 4, bottom: 4 }}
        barSize={16}
      >
        <XAxis type="number" hide domain={[0, 'dataMax']} />
        <YAxis
          type="category"
          dataKey="label"
          width={88}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
        />
        <ChartTooltip
          content={<ChartTooltipContent hideLabel indicator="line" />}
          formatter={(value) => [`${value} of ${total}`, label]}
        />
        <Bar dataKey="count" radius={4} isAnimationActive>
          <LabelList
            dataKey="count"
            position="right"
            fill="var(--muted-foreground)"
            fontSize={11}
          />
          {entries.map((entry) => (
            <Cell key={entry.key} fill={entry.color ?? 'var(--summary-bar)'} />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
