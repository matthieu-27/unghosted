/**
 * Cache-address book for TanStack Query (ADR 0003: keys are arrays rooted
 * by resource, enabling prefix invalidation). Declare each key exactly once.
 */

export const queryKeys = {
  projects: () => ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
  tracker: (id: string) => ['projects', id, 'tracker'] as const,
  documents: (id: string) => ['projects', id, 'documents'] as const,
  profile: (id: string) => ['projects', id, 'profile'] as const,
  mailDraft: (id: string, draftId: string) =>
    ['projects', id, 'mail', 'draft', draftId] as const,
  sentMessages: (id: string) => ['projects', id, 'mail', 'sent'] as const,
  consents: () => ['consents'] as const,
};
