/** Projects dashboard: cards, archive section, empty state, new project. */

import { useQuery } from '@tanstack/react-query';
import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';

import { NewProjectModal } from '@/components/projects/new-project-modal';
import { ProjectCard } from '@/components/projects/project-card';
import { Button } from '@/components/ui/button';
import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import type { ProjectSummary } from '@/lib/tracker-types';

export const Route = createFileRoute('/_authed/projects/')({
  component: ProjectsPage,
});

function archivedProjects(
  payload: { data: ProjectSummary[] } | undefined,
): ProjectSummary[] {
  return (payload?.data ?? []).filter((project) => project.archived);
}

interface ProjectsGridProps {
  projects: ProjectSummary[];
  onCreateFirst: () => void;
}

/** Active project cards, or the first-project empty state. */
function ProjectsGrid({ projects, onCreateFirst }: ProjectsGridProps) {
  if (projects.length === 0) {
    return (
      <section className="mt-8 rounded-lg border p-8 text-center">
        <h2 className="font-semibold">No projects yet</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a template — your tracker comes preconfigured.
        </p>
        <Button className="mt-4" onClick={onCreateFirst}>
          Create your first project
        </Button>
      </section>
    );
  }
  return (
    <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  );
}

function ArchiveSection({
  archived,
  show,
}: {
  archived: ProjectSummary[];
  show: boolean;
}) {
  if (!show) return null;
  return (
    <div className="mt-2 grid gap-4 opacity-70 sm:grid-cols-2 lg:grid-cols-3">
      {archived.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  );
}

function ProjectsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const active = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: () =>
      apiFetch<{ data: ProjectSummary[] }>('/projects?include_archived=false'),
  });
  const archived = useQuery({
    queryKey: queryKeys.projects(),
    queryFn: () =>
      apiFetch<{ data: ProjectSummary[] }>('/projects?include_archived=true'),
    enabled: showArchived,
  });

  if (active.isError) {
    return (
      <main className="container mx-auto p-8">
        <h1 className="text-lg font-semibold">Projects</h1>
        <p role="alert" className="mt-2 text-sm text-red-600">
          Cannot reach the API ({String(active.error)}). Is it running on port
          8000?
        </p>
      </main>
    );
  }

  return (
    <main className="container mx-auto p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">My projects</h1>
        <Button onClick={() => setModalOpen(true)}>+ New project</Button>
      </div>

      <ProjectsGrid
        projects={active.data?.data ?? []}
        onCreateFirst={() => setModalOpen(true)}
      />

      <Button
        variant="ghost"
        className="mt-8"
        aria-expanded={showArchived}
        onClick={() => setShowArchived((v) => !v)}
      >
        Archived ({archivedProjects(archived.data).length})
      </Button>
      <ArchiveSection
        archived={archivedProjects(archived.data)}
        show={showArchived}
      />

      <NewProjectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </main>
  );
}
