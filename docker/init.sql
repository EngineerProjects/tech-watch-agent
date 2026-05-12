-- Tech Watch Agent - PostgreSQL initialization
-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE techwatch TO postgres;

-- Optional: Create specific user for application (uncomment if needed)
-- CREATE USER techwatch_user WITH PASSWORD 'techwatch_password';
-- GRANT ALL PRIVILEGES ON DATABASE techwatch TO techwatch_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO techwatch_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO techwatch_user;