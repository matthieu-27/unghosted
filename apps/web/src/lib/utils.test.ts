import { describe, expect, test } from 'vitest';

import { cn } from './utils';

// Phase 0 smoke test. Route components need the full TanStack Start router
// context and its document shell cannot render inside a jsdom container
// (React rejects that HTML nesting), so screen-level rendering is covered by
// Playwright end-to-end tests from phase 2 on. This file verifies the test
// toolchain and the class-merging util every component relies on.
describe('cn', () => {
  test('merges conditional classes and drops falsy values', () => {
    expect(cn('px-2', false && 'hidden', undefined, 'py-1')).toBe('px-2 py-1');
  });

  test('resolves Tailwind conflicts keeping the last class', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });
});
