import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge conditional class names and resolve Tailwind class conflicts.
 * Standard shadcn/ui helper — the single place class composition happens.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
