# 1 — Projects

1. **Create project.** As a user I create a project from a template so the tracker is preconfigured.
   AC: modal offers `apprenticeship-search` and `rental-search`. Template settings validated against the template schema. Project appears in Mongo (definition) and Postgres (project row) with documented write order.
2. **Dashboard.** AC: cards show name, template, key numbers, last activity. Active and archived projects separated. Empty state invites first project.
3. **Open workspace.** AC: left rail sections are URL state. Deep link restores section, sort, filters. Top chrome ≤ 150 px.
4. **Archive / duplicate / rename / delete.** AC: archive hides from active list. Duplicate copies definition + rows. Delete is soft, purged by retention job.
