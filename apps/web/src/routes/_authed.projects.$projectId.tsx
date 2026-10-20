/** Project workspace shell: identity + section nav shared by every project
 * area (tracker, contacts, documents, mail). The pages own their toolbars;
 * this owns the "where am I" layer — name, sections, and a container that
 * keeps page content aligned on one max width. */

import {
  ArrowLeftIcon,
  Contact01Icon,
  File01Icon,
  Mail01Icon,
  Table01Icon,
} from '@hugeicons/core-free-icons';
import { HugeiconsIcon } from '@hugeicons/react';
import { useQuery } from '@tanstack/react-query';
import { createFileRoute, Link, Outlet } from '@tanstack/react-router';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { ProjectSummary } from '@/lib/tracker-types';

export const Route = createFileRoute('/_authed/projects/$projectId')({
  component: ProjectWorkspace,
});

const SECTIONS = [
  { to: '/projects/$projectId/tracker', label: 'Tracker', icon: Table01Icon },
  {
    to: '/projects/$projectId/contacts',
    label: 'Contacts',
    icon: Contact01Icon,
  },
  {
    to: '/projects/$projectId/documents',
    label: 'Documents',
    icon: File01Icon,
  },
  { to: '/projects/$projectId/mail', label: 'Mail', icon: Mail01Icon },
] as const;

function ProjectWorkspace() {
  const { projectId } = Route.useParams();
  const project = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => apiFetch<ProjectSummary>(`/projects/${projectId}`),
  });
  const name = project.data?.name ?? '…';

  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-20 border-b bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-4 pt-3 sm:px-6">
          <div className="flex animate-in fade-in slide-in-from-bottom-1 items-center gap-3 duration-300">
            <Link
              to="/projects"
              aria-label="Back to projects"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <HugeiconsIcon icon={ArrowLeftIcon} strokeWidth={2} />
            </Link>
            <h1 className="min-w-0 truncate font-serif text-xl font-semibold tracking-tight sm:text-2xl">
              {name}
            </h1>
          </div>
          <nav aria-label="Project sections" className="-mb-px flex gap-1">
            {SECTIONS.map((section) => (
              <Link
                key={section.to}
                to={section.to}
                params={{ projectId }}
                activeOptions={{ exact: true }}
                className="inline-flex items-center gap-1.5 border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground transition-colors hover:border-border hover:text-foreground"
                activeProps={{
                  className: 'border-primary text-foreground',
                }}
              >
                <HugeiconsIcon
                  icon={section.icon}
                  strokeWidth={2}
                  className="size-4"
                />
                {section.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
