/** Contact wire types, mirroring the API payloads (us-7). */

export interface Contact {
  id: string;
  name: string;
  role: string | null;
  organization: string | null;
  email: string | null;
  phone: string | null;
  profile_url: string | null;
  notes: string | null;
  linked_row_count: number;
  created_at: string;
  updated_at: string;
}

export interface ContactList {
  data: Contact[];
}

export interface ContactThread {
  id: string;
  recipient: string;
  message_count: number;
  last_message_at: string | null;
}

export interface ContactDetail {
  contact: Contact;
  linked_row_ids: string[];
  threads: ContactThread[];
}

/** Editable fields, as the create and patch bodies carry them. A null
 * clears the field, an absent key keeps it (the API's PATCH contract). */
export interface ContactInput {
  name?: string;
  role?: string | null;
  organization?: string | null;
  email?: string | null;
  phone?: string | null;
  profile_url?: string | null;
  notes?: string | null;
}
