-- Add thread_id column to projects table
ALTER TABLE app.projects ADD COLUMN IF NOT EXISTS thread_id VARCHAR(255);
