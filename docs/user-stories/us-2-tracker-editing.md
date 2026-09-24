# 2 — Tracker editing

[← All user stories](./README.md)

1. **Edit cell.** As a user I click or keyboard-navigate to a cell and type so data entry is fast.
   AC: editor matches column type (date picker, select, checkbox, rating…). Enter commits, Escape cancels. Tab/arrows navigate (WAI-ARIA grid pattern). Edits batch and autosave after edits. Save status shown.
2. **Copy/paste.** AC: copy/paste as tab-separated text. Range selection supported. Paste into typed columns validates and rejects invalid values with a message.
3. **Rows.** AC: insert above/below, delete, duplicate, move. Virtualization keeps DOM rows bounded (10 000 rows scroll without lag).
4. **Columns.** AC: add column with picked type. Resize. Reorder. Delete. Computed columns read-only.
5. **Revision conflicts.** AC: concurrent edit on stale revision returns 409 with rebase data. Client rebases or reloads. Worker writes go through the same operations path with system author.
6. **Undo/redo.** AC: client-side over the operation log. Undo restores previous cell value and style. Redo re-applies.
