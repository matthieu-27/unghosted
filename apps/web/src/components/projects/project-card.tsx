/** Dashboard project card (user stories, section 2, item 2). */

import { Link } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { ProjectSummary } from '@/lib/tracker-types';

const TEMPLATE_LABELS: Record<string, string> = {
  'apprenticeship-search': 'Apprenticeship search',
  'rental-search': 'Rental search',
};

export function ProjectCard({ project }: { project: ProjectSummary }) {
  return (
    <Link
      to="/projects/$projectId/tracker"
      params={{ projectId: project.id }}
      className="block rounded-lg focus-visible:outline-2"
    >
      <Card className="h-full transition-colors hover:bg-accent">
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">{project.name}</CardTitle>
            {project.archived ? (
              <Badge variant="secondary">Archived</Badge>
            ) : null}
          </div>
          <CardDescription>
            {TEMPLATE_LABELS[project.template_key] ?? project.template_key}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {project.description ? (
            <p className="line-clamp-2 text-sm">{project.description}</p>
          ) : null}
          <p className="mt-2 text-xs text-muted-foreground">
            updated {new Date(project.updated_at).toLocaleDateString()}
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}
