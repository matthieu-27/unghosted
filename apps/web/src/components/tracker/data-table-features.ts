/**
 * TanStack Table v9 feature registration for the tracker grid (shadcn
 * data-table recipe pattern). Explicit registration tree-shakes unused
 * features; a feature used but not registered fails visibly (ADR 0004).
 */
import { cellSelectionFeature, tableFeatures } from '@tanstack/react-table';

export const features = tableFeatures({
  cellSelectionFeature,
});
