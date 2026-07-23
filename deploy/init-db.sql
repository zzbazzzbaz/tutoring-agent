CREATE EXTENSION IF NOT EXISTS vector;

SELECT 'CREATE DATABASE tutoring_agent_server_db'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'tutoring_agent_server_db'
)\gexec

\connect tutoring_agent_server_db
CREATE EXTENSION IF NOT EXISTS vector;
