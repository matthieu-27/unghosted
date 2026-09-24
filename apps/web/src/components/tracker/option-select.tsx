/**
 * Shared Select wired to a column's options list (clone found by the audit:
 * cell-editors and review-form rendered the same SelectContent block).
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ColumnDefinition } from '@/lib/tracker-types';

interface OptionSelectProps {
  column: ColumnDefinition;
  value?: string | null;
  onValueChange: (value: string | null) => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  triggerId?: string;
  triggerClassName?: string;
  autoFocus?: boolean;
}

export function OptionSelect({
  column,
  value,
  onValueChange,
  open,
  onOpenChange,
  triggerId,
  triggerClassName,
  autoFocus,
}: OptionSelectProps) {
  return (
    <Select
      open={open}
      onOpenChange={onOpenChange}
      value={value}
      onValueChange={onValueChange}
    >
      <SelectTrigger
        id={triggerId}
        className={triggerClassName}
        autoFocus={autoFocus}
      >
        <SelectValue placeholder="—" />
      </SelectTrigger>
      <SelectContent>
        {column.options?.map((option) => (
          <SelectItem key={option.key} value={option.key}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
