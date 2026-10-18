/**
 * Project template data and form-value coercion for the New Project modal:
 * string form inputs become the wire types the API expects.
 */

export interface TemplateChoice {
  key: string;
  label: string;
  description: string;
  settings: { key: string; label: string; type: 'date' | 'number' | 'text' }[];
}

export const TEMPLATES: TemplateChoice[] = [
  {
    key: 'apprenticeship-search',
    label: 'Apprenticeship search',
    description: 'Track work-study applications: interviews, follow-ups.',
    settings: [
      { key: 'contract_end_date', label: 'Contract end date', type: 'date' },
      {
        key: 'no_response_threshold_days',
        label: 'No-response threshold (days)',
        type: 'number',
      },
    ],
  },
  {
    key: 'rental-search',
    label: 'Rental search',
    description: 'Track apartment listings, visits, application files.',
    settings: [
      {
        key: 'max_budget_rent',
        label: 'Max budget (rent incl. charges)',
        type: 'number',
      },
      { key: 'target_area', label: 'Target area', type: 'text' },
      {
        key: 'target_move_in_date',
        label: 'Target move-in date',
        type: 'date',
      },
    ],
  },
];

// Settings the API stores as numbers, not strings.
const NUMERIC_SETTING_KEYS: ReadonlySet<string> = new Set([
  'no_response_threshold_days',
  'max_budget_rent',
]);

/** One setting's wire value: numbers for numeric settings, raw string
 * otherwise. */
function coercedValue(key: string, value: string): string | number {
  if (NUMERIC_SETTING_KEYS.has(key)) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return value;
}

/** Drops empty entries and coerces numeric settings to finite numbers,
 * leaving anything unparsable as the raw string. */
export function coerceSettings(
  raw: Record<string, string>,
): Record<string, string | number> {
  const result: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (value === '') continue;
    result[key] = coercedValue(key, value);
  }
  return result;
}
