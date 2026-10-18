/**
 * Applicant-profile editor (us-4 item 3): draft regeneration, editing of the
 * current draft, approval. Approved versions render read-only — the API
 * refuses edits on them and regeneration never overwrites one.
 */

import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type {
  ProfileContentUpdateBody,
  ProfileHighlightItem,
  ProfileState,
  ProfileVersion,
} from '@/lib/tracker-types';

interface ProfileEditorProps {
  state: ProfileState;
  drafting: boolean;
  saving: boolean;
  approving: boolean;
  error: string | null;
  onDraft: () => void;
  onSave: (version: number, body: ProfileContentUpdateBody) => void;
  onApprove: (version: number) => void;
}

export function ProfileEditor({
  state,
  drafting,
  saving,
  approving,
  error,
  onDraft,
  onSave,
  onApprove,
}: ProfileEditorProps) {
  const draft = state.draft;
  return (
    <section aria-label="Applicant profile">
      {state.approved ? (
        <ApprovedVersion version={state.approved} />
      ) : (
        <p className="text-xs text-muted-foreground">
          No approved profile yet.
        </p>
      )}

      {error ? (
        <p role="alert" className="mt-2 text-xs text-red-600">
          {error}
        </p>
      ) : null}

      <div className="mt-3 flex gap-2">
        <Button type="button" disabled={drafting} onClick={onDraft}>
          {drafting
            ? 'Drafting…'
            : draft
              ? 'Regenerate draft'
              : 'Generate draft from documents'}
        </Button>
      </div>

      {draft ? (
        // Keyed by version: a regenerated draft resets the form fields.
        <DraftForm
          key={draft.version}
          draft={draft}
          saving={saving}
          approving={approving}
          onSave={onSave}
          onApprove={onApprove}
        />
      ) : null}
    </section>
  );
}

function ApprovedVersion({ version }: { version: ProfileVersion }) {
  return (
    <div className="rounded-md border border-foreground/10 p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium">
          Approved (version {version.version})
        </h3>
        <Badge>{version.status}</Badge>
      </div>
      <dl className="mt-2 space-y-1 text-xs/relaxed">
        <dt className="font-medium">Headline</dt>
        <dd>{version.headline ?? '—'}</dd>
        <dt className="font-medium">Seeking</dt>
        <dd>{version.seeking ?? '—'}</dd>
        <dt className="font-medium">Motivation</dt>
        <dd>{version.motivation ?? '—'}</dd>
        <dt className="font-medium">Availability</dt>
        <dd>{version.availability ?? '—'}</dd>
        <dt className="font-medium">Highlights</dt>
        <dd>
          <ul className="list-disc pl-4">
            {version.highlights.map((h) => (
              <li key={h.id}>{h.text}</li>
            ))}
          </ul>
        </dd>
        <dt className="font-medium">Style notes</dt>
        <dd>
          <ul className="list-disc pl-4">
            {version.style_notes.map((s) => (
              <li key={s.id}>{s.text}</li>
            ))}
          </ul>
        </dd>
      </dl>
    </div>
  );
}

interface DraftFormProps {
  draft: ProfileVersion;
  saving: boolean;
  approving: boolean;
  onSave: (version: number, body: ProfileContentUpdateBody) => void;
  onApprove: (version: number) => void;
}

function DraftForm({
  draft,
  saving,
  approving,
  onSave,
  onApprove,
}: DraftFormProps) {
  const [headline, setHeadline] = useState(draft.headline ?? '');
  const [seeking, setSeeking] = useState(draft.seeking ?? '');
  const [motivation, setMotivation] = useState(draft.motivation ?? '');
  const [availability, setAvailability] = useState(draft.availability ?? '');
  const [highlights, setHighlights] = useState<ProfileHighlightItem[]>(
    draft.highlights,
  );
  const [styleNotes, setStyleNotes] = useState<ProfileHighlightItem[]>(
    draft.style_notes,
  );

  function commit() {
    // Absent fields keep their stored value (wire contract), so only the
    // non-empty ones travel.
    const body: ProfileContentUpdateBody = {};
    if (headline !== '') body.headline = headline;
    if (seeking !== '') body.seeking = seeking;
    if (motivation !== '') body.motivation = motivation;
    if (availability !== '') body.availability = availability;
    if (highlights.length > 0) body.highlights = highlights;
    if (styleNotes.length > 0) body.style_notes = styleNotes;
    onSave(draft.version, body);
  }

  return (
    <div className="mt-3 rounded-md border border-foreground/10 p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium">Draft (version {draft.version})</h3>
        <Badge variant="outline">editable</Badge>
      </div>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="profile-headline">Headline</FieldLabel>
          <Input
            id="profile-headline"
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="profile-seeking">Seeking</FieldLabel>
          <Input
            id="profile-seeking"
            value={seeking}
            onChange={(e) => setSeeking(e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="profile-motivation">Motivation</FieldLabel>
          <Textarea
            id="profile-motivation"
            rows={3}
            value={motivation}
            onChange={(e) => setMotivation(e.target.value)}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="profile-availability">Availability</FieldLabel>
          <Input
            id="profile-availability"
            value={availability}
            onChange={(e) => setAvailability(e.target.value)}
          />
        </Field>
        <HighlightList
          label="Highlights"
          items={highlights}
          onChange={setHighlights}
        />
        <HighlightList
          label="Style notes"
          items={styleNotes}
          onChange={setStyleNotes}
        />
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={saving}
            onClick={commit}
          >
            {saving ? 'Saving…' : 'Save draft'}
          </Button>
          <Button
            type="button"
            disabled={approving}
            onClick={() => onApprove(draft.version)}
          >
            {approving ? 'Approving…' : 'Approve this version'}
          </Button>
        </div>
      </FieldGroup>
    </div>
  );
}

interface HighlightListProps {
  label: string;
  items: ProfileHighlightItem[];
  onChange: (items: ProfileHighlightItem[]) => void;
}

function HighlightList({ label, items, onChange }: HighlightListProps) {
  function update(index: number, text: string) {
    onChange(items.map((item, i) => (i === index ? { ...item, text } : item)));
  }
  function remove(index: number) {
    onChange(items.filter((_, i) => i !== index));
  }
  function add() {
    onChange([...items, { id: `local-${crypto.randomUUID()}`, text: '' }]);
  }
  return (
    <Field>
      <FieldLabel>{label}</FieldLabel>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={item.id} className="flex items-center gap-2">
            <Input
              aria-label={`${label} ${index + 1}`}
              value={item.text}
              onChange={(e) => update(index, e.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label={`Remove ${label.toLowerCase()} ${index + 1}`}
              onClick={() => remove(index)}
            >
              Remove
            </Button>
          </div>
        ))}
        <div>
          <Button type="button" variant="outline" size="sm" onClick={add}>
            Add
          </Button>
        </div>
      </div>
    </Field>
  );
}
