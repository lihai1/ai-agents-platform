-- Remove thread_id column from projects table
ALTER TABLE app.projects DROP COLUMN IF EXISTS thread_id;
