/**
 * Account creation (user stories, section 6, item 1). Password rules and
 * duplicate-email detection come from Better Auth; this form only relays
 * them in plain words.
 */

import { useForm } from '@tanstack/react-form';
import { useNavigate, useRouter } from '@tanstack/react-router';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { signUp } from '@/lib/auth-client';

function signupMessage(code: string | undefined, message: string | undefined) {
  if (code === 'USER_ALREADY_EXISTS') {
    return 'An account already uses this email address.';
  }
  return message ?? 'Account creation failed.';
}

export function SignupForm() {
  const navigate = useNavigate();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: { name: '', email: '', password: '' },
    onSubmit: async ({ value }) => {
      setFormError(null);
      const { error } = await signUp.email({
        name: value.name,
        email: value.email,
        password: value.password,
      });
      if (error) {
        setFormError(signupMessage(error.code, error.message));
        return;
      }
      await router.invalidate();
      await navigate({ to: '/projects' });
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        void form.handleSubmit();
      }}
    >
      <FieldGroup>
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
              <FieldLabel htmlFor="signup-name">Name</FieldLabel>
              <Input
                id="signup-name"
                autoComplete="name"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                aria-invalid={field.state.meta.errors.length > 0}
              />
              {field.state.meta.errors[0] ? (
                <FieldError>{String(field.state.meta.errors[0])}</FieldError>
              ) : null}
            </Field>
          )}
        </form.Field>

        <form.Field
          name="email"
          validators={{
            onChange: ({ value }) =>
              value.trim() ? undefined : 'Email is required',
          }}
        >
          {(field) => (
            <Field
              data-invalid={
                field.state.meta.errors.length > 0 ? 'true' : undefined
              }
            >
              <FieldLabel htmlFor="signup-email">Email</FieldLabel>
              <Input
                id="signup-email"
                type="email"
                autoComplete="email"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                aria-invalid={field.state.meta.errors.length > 0}
              />
              {field.state.meta.errors[0] ? (
                <FieldError>{String(field.state.meta.errors[0])}</FieldError>
              ) : null}
            </Field>
          )}
        </form.Field>

        <form.Field
          name="password"
          validators={{
            onChange: ({ value }) =>
              value.length >= 8
                ? undefined
                : 'Password must be at least 8 characters',
          }}
        >
          {(field) => (
            <Field
              data-invalid={
                field.state.meta.errors.length > 0 ? 'true' : undefined
              }
            >
              <FieldLabel htmlFor="signup-password">Password</FieldLabel>
              <Input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                aria-invalid={field.state.meta.errors.length > 0}
              />
              {field.state.meta.errors[0] ? (
                <FieldError>{String(field.state.meta.errors[0])}</FieldError>
              ) : null}
            </Field>
          )}
        </form.Field>

        {formError ? (
          <p role="alert" className="text-sm text-destructive">
            {formError}
          </p>
        ) : null}

        <form.Subscribe selector={(state) => state.isSubmitting}>
          {(isSubmitting) => (
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </Button>
          )}
        </form.Subscribe>
      </FieldGroup>
    </form>
  );
}
