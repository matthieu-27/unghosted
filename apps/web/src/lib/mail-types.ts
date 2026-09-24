/** Mail wire types, mirroring the API payloads (us-5). */

export type MailDraftKind = 'customised_letter' | 'first_contact_email';
export type MailDraftStatus = 'draft' | 'approved' | 'sent' | 'discarded';
export type MailLanguage = 'fr' | 'en';

export interface MailWarning {
  code: string;
  message: string;
}

export interface MailDraft {
  id: string;
  kind: MailDraftKind;
  status: MailDraftStatus;
  row_id: string;
  recipient: string | null;
  contact_name: string | null;
  subject: string | null;
  text: string | null;
  used_highlights: string[];
  attachment_document_ids: string[];
  letter_document_id: string | null;
  warnings: MailWarning[];
  created_at: string;
  updated_at: string;
}

export interface ApprovedLetter {
  draft: MailDraft;
  document_id: string;
  fits_one_page: boolean;
}

export interface SentEmail {
  message_id: string;
  thread_id: string;
  draft_id: string;
  sender: string;
  recipient: string;
  subject: string;
  provider: string;
  provider_message_id: string | null;
  provider_thread_id: string | null;
  attachment_document_ids: string[];
  sent_at: string;
  row_revision: number;
}

export interface SentMessage {
  id: string;
  thread_id: string;
  row_id: string | null;
  sender: string;
  recipient: string;
  subject: string;
  direction: string;
  provider: string;
  provider_message_id: string | null;
  attachment_document_ids: string[];
  sent_at: string;
  text: string | null;
}

export interface SentMessageList {
  data: SentMessage[];
}

export interface LetterDraftBody {
  contact_name?: string;
  language?: MailLanguage;
}

export interface FirstContactDraftBody {
  recipient: string;
  contact_name?: string;
  language?: MailLanguage;
}

/** PATCH body: absent fields keep their stored value. */
export interface DraftUpdateBody {
  recipient?: string;
  contact_name?: string;
  subject?: string;
  text?: string;
  attachment_document_ids?: string[];
}

export interface SendBody {
  sender?: string;
}
