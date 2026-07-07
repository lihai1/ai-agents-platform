-- Create app schema
CREATE SCHEMA IF NOT EXISTS app;

-- Users table
CREATE TABLE IF NOT EXISTS app.users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Organizations table
CREATE TABLE IF NOT EXISTS app.organizations (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Projects table
CREATE TABLE IF NOT EXISTS app.projects (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES app.organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Repositories table
CREATE TABLE IF NOT EXISTS app.repositories (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES app.projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    git_url TEXT NOT NULL,
    branch VARCHAR(255) DEFAULT 'main',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON app.users(email);
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON app.organizations(slug);
CREATE INDEX IF NOT EXISTS idx_projects_organization_id ON app.projects(organization_id);
CREATE INDEX IF NOT EXISTS idx_repositories_project_id ON app.repositories(project_id);
