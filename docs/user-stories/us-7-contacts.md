# 7 — Contacts

[← All user stories](./README.md)

1. **CRUD.** AC: fields per naming table. Per project only. Search. Detail panel lists linked rows and threads.
2. **Contact link column.** AC: row links one or more contacts. Unlink keeps contact. First-contact email requires linked contact with email.
3. **Cross-store consistency.** AC: deleting a contact removes row links in Postgres and cleans Mongo cells via compensation. Reconciliation command reports orphans.
