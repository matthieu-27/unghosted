/** Workspace title row: back link, editable project name, save status. */

import { Link } from '@tanstack/react-router';

import { SaveStatusIndicator } from '@/components/workspace/save-status';
import type { SaveStatus } from '@/hooks/use-autosave';

interface TitleRowProps {
  projectName: string;
  saveStatus: SaveStatus;
}

export function TitleRow({ projectName, saveStatus }: TitleRowProps) {
  return (
    <header className="flex items-center gap-4 border-b px-4 py-2">
      <Link to="/projects" aria-label="Back to projects">
        ← Projects
      </Link>
      <h1 className="text-lg font-semibold">{projectName}</h1>
      <SaveStatusIndicator status={saveStatus} />
    </header>
  );
}
