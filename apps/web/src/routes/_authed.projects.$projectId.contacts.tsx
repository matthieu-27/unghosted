/** Contacts route: search, list, detail panel for one project (us-7). */

import { createFileRoute } from '@tanstack/react-router';

import { ContactsPage } from '@/components/contacts/contacts-page';

/** Panel state lives in the URL (ADR 0003): ?contact=… opens the detail. */
interface ContactsSearch {
  contact: string | undefined;
}

export const Route = createFileRoute('/_authed/projects/$projectId/contacts')({
  validateSearch: (search: Record<string, unknown>): ContactsSearch => ({
    contact: typeof search.contact === 'string' ? search.contact : undefined,
  }),
  component: ContactsRoute,
});

function ContactsRoute() {
  const { projectId } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  return (
    <ContactsPage
      projectId={projectId}
      selectedContactId={search.contact ?? null}
      onSelectContact={(contactId) => {
        void navigate({ search: { contact: contactId } });
      }}
      onClearContact={() => {
        void navigate({ search: { contact: undefined } });
      }}
    />
  );
}
