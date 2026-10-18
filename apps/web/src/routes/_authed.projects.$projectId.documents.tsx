/** Documents route: passes the project id to the page body (us-4). */

import { createFileRoute } from '@tanstack/react-router';

import { DocumentsPage } from '@/components/documents/documents-page';

export const Route = createFileRoute('/_authed/projects/$projectId/documents')({
  component: RouteComponent,
});

function RouteComponent() {
  const { projectId } = Route.useParams();
  return <DocumentsPage projectId={projectId} />;
}
