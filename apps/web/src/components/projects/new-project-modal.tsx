/**
 * New project modal: template pick + name + description + template settings
 * (user stories, section 2, item 1). TanStack Form drives validation,
 * shadcn Field primitives drive layout and inputs.
 */

import { useForm } from '@tanstack/react-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';
import { coerceSettings, TEMPLATES } from '@/lib/project-settings';
import { queryKeys } from '@/lib/query-keys';
import type { ProjectSummary } from '@/lib/tracker-types';

interface NewProjectModalProps {
  open: boolean;
  onClose: () => void;
}

/** First template preselected, blank when the list is somehow empty. */
function defaultTemplateKey(): string {
  return TEMPLATES[0]?.key ?? '';
}

interface SettingsFieldsProps {
  settings: { key: string; label: string; type: 'date' | 'number' | 'text' }[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

/** One input per template setting. */
function SettingsFields({ settings, values, onChange }: SettingsFieldsProps) {
  return settings.map((setting) => (
    <Field key={setting.key}>
      <FieldLabel htmlFor={`setting-${setting.key}`}>
        {setting.label}
      </FieldLabel>
      <Input
        id={`setting-${setting.key}`}
        type={setting.type}
        value={values[setting.key] ?? ''}
        onChange={(e) => onChange(setting.key, e.target.value)}
      />
    </Field>
  ));
}

export function NewProjectModal({ open, onClose }: NewProjectModalProps) {
  const queryClient = useQueryClient();
  const [templateKey, setTemplateKey] = useState(defaultTemplateKey());
  const [settings, setSettings] = useState<Record<string, string>>({});

  const create = useMutation({
    mutationFn: (values: { name: string; description: string }) =>
      apiFetch<ProjectSummary>('/projects', {
        method: 'POST',
        body: JSON.stringify({
          template_key: templateKey,
          name: values.name,
          description: values.description || null,
          settings: coerceSettings(settings),
        }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      onClose();
    },
  });

  const form = useForm({
    defaultValues: { name: '', description: '' },
    onSubmit: ({ value }) => create.mutateAsync(value),
  });

  if (!open) return null;
  const template = TEMPLATES.find((t) => t.key === templateKey);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="New project"
        className="w-full max-w-lg rounded-lg bg-background p-6 shadow-xl"
      >
        <h2 className="text-lg font-semibold">New project</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
            void form.handleSubmit();
          }}
          className="mt-4"
        >
          <FieldGroup>
            <FieldSet>
              <FieldLegend>Template</FieldLegend>
              <RadioGroup
                value={templateKey}
                onValueChange={setTemplateKey}
                className="gap-2"
              >
                {TEMPLATES.map((t) => (
                  <div key={t.key} className="flex items-start gap-2">
                    <RadioGroupItem id={`template-${t.key}`} value={t.key} />
                    <label
                      htmlFor={`template-${t.key}`}
                      className="cursor-pointer"
                    >
                      <span className="font-medium">{t.label}</span>
                      <span className="block text-sm text-muted-foreground">
                        {t.description}
                      </span>
                    </label>
                  </div>
                ))}
              </RadioGroup>
            </FieldSet>

            <form.Field
              name="name"
              validators={{
                onChange: ({ value }) =>
                  value.trim() ? undefined : 'Name is required',
              }}
            >
              {(field) => (
                <Field
                  data-invalid={
                    field.state.meta.errors.length > 0 ? 'true' : undefined
                  }
                >
                  <FieldLabel htmlFor="project-name">Name</FieldLabel>
                  <Input
                    id="project-name"
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    aria-invalid={field.state.meta.errors.length > 0}
                  />
                  {field.state.meta.errors[0] ? (
                    <FieldError>
                      {String(field.state.meta.errors[0])}
                    </FieldError>
                  ) : null}
                </Field>
              )}
            </form.Field>

            <form.Field name="description">
              {(field) => (
                <Field>
                  <FieldLabel htmlFor="project-description">
                    Description
                  </FieldLabel>
                  <Textarea
                    id="project-description"
                    rows={2}
                    value={field.state.value}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                  />
                </Field>
              )}
            </form.Field>

            {template ? (
              <SettingsFields
                settings={template.settings}
                values={settings}
                onChange={(key, value) =>
                  setSettings((current) => ({ ...current, [key]: value }))
                }
              />
            ) : null}

            {create.isError ? (
              <FieldError>{String(create.error)}</FieldError>
            ) : null}

            <div className="mt-2 flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={create.isPending}>
                Create project
              </Button>
            </div>
          </FieldGroup>
        </form>
      </div>
    </div>
  );
}
