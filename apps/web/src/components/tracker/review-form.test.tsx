import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ColumnDefinition, LinkAnalysisResult } from '@/lib/tracker-types';
import { ReviewForm } from './review-form';

afterEach(cleanup);

const columns: ColumnDefinition[] = [
  { key: 'company', type: 'text', label: 'Company' },
  {
    key: 'status',
    type: 'select',
    label: 'Status',
    options: [
      { key: 'to_apply', label: 'To apply' },
      { key: 'sent', label: 'Sent' },
    ],
  },
  { key: 'date_sent', type: 'date', label: 'Date sent' },
  { key: 'salary_offered', type: 'currency', label: 'Salary offered' },
  { key: 'notes', type: 'long-text', label: 'Notes' },
  { key: 'response_date', type: 'date', label: 'Response date', system: true },
  { key: 'days_since_sent', type: 'computed', label: 'Days', computed: 'x' },
];

function result(
  overrides: Partial<LinkAnalysisResult> = {},
): LinkAnalysisResult {
  return {
    page_kind: 'job_offer',
    page_kind_confidence: 'high',
    page_kind_basis: 'jsonld',
    provider: null,
    cached: false,
    fields: [
      { column_key: 'company', value: 'Acme SAS', provenance: 'structured' },
      { column_key: 'status', value: 'to_apply', provenance: 'detection' },
    ],
    warnings: [],
    ...overrides,
  };
}

describe('ReviewForm', () => {
  it('pre-fills extracted values and shows their provenance', () => {
    render(
      <ReviewForm
        columns={columns}
        result={result()}
        saving={false}
        error={null}
        onKindChange={vi.fn()}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const company = screen.getByLabelText(/Company/) as HTMLInputElement;
    expect(company.value).toBe('Acme SAS');
    expect(screen.getByText('structured data')).toBeTruthy();
    expect(screen.getByText('detection')).toBeTruthy();
  });

  it('never renders system or computed columns', () => {
    render(
      <ReviewForm
        columns={columns}
        result={result()}
        saving={false}
        error={null}
        onKindChange={vi.fn()}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText(/Response date/)).toBeNull();
    expect(screen.queryByLabelText(/Days/)).toBeNull();
  });

  it('lists warnings as an alert', () => {
    render(
      <ReviewForm
        columns={columns}
        result={result({
          warnings: [
            { code: 'duplicate_url', detail: 'a row already lists this URL' },
          ],
        })}
        saving={false}
        error={null}
        onKindChange={vi.fn()}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByRole('alert')?.textContent).toContain(
      'a row already lists this URL',
    );
  });

  it('commits only non-empty values with numeric coercion', () => {
    const onSave = vi.fn();
    render(
      <ReviewForm
        columns={columns}
        result={result()}
        saving={false}
        error={null}
        onKindChange={vi.fn()}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Salary offered/), {
      target: { value: '45000' },
    });
    fireEvent.change(screen.getByLabelText(/Date sent/), {
      target: { value: '2026-09-22' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save row' }));
    expect(onSave).toHaveBeenCalledWith({
      kind: 'job_offer',
      cells: {
        company: 'Acme SAS',
        status: 'to_apply',
        salary_offered: 45000,
        date_sent: '2026-09-22',
      },
    });
  });

  it('disables save while saving', () => {
    render(
      <ReviewForm
        columns={columns}
        result={result()}
        saving={true}
        error={null}
        onKindChange={vi.fn()}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(
      screen.getByRole('button', { name: 'Saving…' }).hasAttribute('disabled'),
    ).toBe(true);
  });
});
