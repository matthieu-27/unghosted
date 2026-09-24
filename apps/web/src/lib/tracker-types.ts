/** Tracker wire types, mirroring the API payloads (docs/api-contract.md). */

export type ColumnType =
  | 'text'
  | 'long-text'
  | 'number'
  | 'currency'
  | 'percent'
  | 'date'
  | 'select'
  | 'checkbox'
  | 'url'
  | 'email'
  | 'phone'
  | 'rating'
  | 'contact-link'
  | 'document-link'
  | 'computed';

export interface SelectOption {
  key: string;
  label: string;
  color?: string | null;
}

export interface ColumnDefinition {
  key: string;
  type: ColumnType;
  label: string;
  system?: boolean;
  options?: SelectOption[];
  currency?: string;
  max?: number;
  computed?: string;
  width?: number;
}

export interface TrackerRow {
  id: string;
  order_key: string;
  cells: Record<string, unknown>;
}

export interface TrackerDefinition {
  template_key: string;
  template_version: number;
  revision: number;
  columns: ColumnDefinition[];
  conditional_rules: unknown[];
  settings: Record<string, unknown>;
}

export interface TrackerPayload {
  definition: TrackerDefinition;
  rows: TrackerRow[];
}

export interface DocumentTypeSummary {
  key: string;
  label: string;
  model_eligible: boolean;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string | null;
  template_key: string;
  template_version: number;
  archived: boolean;
  document_types: DocumentTypeSummary[];
  created_at: string;
  updated_at: string;
}

export type TrackerOperation =
  | { op: 'set_cell'; row_id: string; column_key: string; value?: unknown }
  | { op: 'insert_rows'; after_row_id?: string | null; count: number }
  | { op: 'delete_rows'; row_ids: string[] };

/** Link analysis ("+ New application", user story 3). */

export const PAGE_KIND_LABELS: Record<string, string> = {
  job_offer: 'Job offer',
  company: 'Company',
  careers: 'Careers',
  school_program: 'School program',
  housing_listing: 'Housing listing',
  agency: 'Agency',
  other: 'Other',
};

export interface ExtractedField {
  column_key: string;
  value: unknown;
  provenance: 'structured' | 'meta' | 'model' | 'detection' | 'manual';
}

export interface AnalysisWarning {
  code: string;
  detail: string;
}

export interface LinkAnalysisResult {
  page_kind: string | null;
  page_kind_confidence: string | null;
  page_kind_basis: string | null;
  provider: string | null;
  cached: boolean;
  fields: ExtractedField[];
  warnings: AnalysisWarning[];
}

export interface LinkAnalysisBody {
  input: string;
  force_kind?: string | null;
}

/** Documents and applicant profile (us-4). */

export interface DocumentSummary {
  id: string;
  type_key: string;
  model_eligible: boolean;
  original_filename: string;
  size_bytes: number;
  created_at: string;
}

export interface DocumentList {
  data: DocumentSummary[];
}

export interface ConsentSummary {
  kind: string;
  granted_at: string;
  withdrawn_at: string | null;
}

export interface ConsentList {
  data: ConsentSummary[];
}

export interface ProfileHighlightItem {
  id: string;
  text: string;
}

export interface ProfileVersion {
  version: number;
  status: 'draft' | 'approved' | 'superseded';
  headline: string | null;
  seeking: string | null;
  highlights: ProfileHighlightItem[];
  motivation: string | null;
  style_notes: ProfileHighlightItem[];
  availability: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileState {
  approved: ProfileVersion | null;
  draft: ProfileVersion | null;
  versions: ProfileVersion[];
}

/** PATCH body for a draft version. Absent fields keep their current value. */
export interface ProfileContentUpdateBody {
  headline?: string;
  seeking?: string;
  highlights?: ProfileHighlightItem[];
  motivation?: string;
  style_notes?: ProfileHighlightItem[];
  availability?: string;
}
