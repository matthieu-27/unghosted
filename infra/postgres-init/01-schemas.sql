-- Schemas the two migration owners expect to exist.
-- `app`: Alembic (Python API). `auth`: Better Auth's own CLI migrations.
-- Runs once, on an empty data volume. Existing volumes need the same two
-- statements by hand (see docs/user-stories/us-6 notes in the README).
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS auth;
