-- Alpha Pro MENA CRM — PostgreSQL initialization
-- This file runs once when the container is first created.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create a read-only audit_logs role (prevents UPDATE/DELETE on audit table)
-- This is applied after migrations via backend startup
