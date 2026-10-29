-- SQL Setup Script for AI Interviewer local database and user
-- Execute this script as the postgres administrator

DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ai_interviewer_user'
   ) THEN
      CREATE ROLE ai_interviewer_user WITH LOGIN PASSWORD 'ai_interview_secure_pass_2026';
   ELSE
      ALTER ROLE ai_interviewer_user WITH PASSWORD 'ai_interview_secure_pass_2026';
   END IF;
END
$do$;

-- Create database if it does not exist
SELECT 'CREATE DATABASE ai_interviewer_db OWNER ai_interviewer_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_interviewer_db')\gexec

GRANT ALL PRIVILEGES ON DATABASE ai_interviewer_db TO ai_interviewer_user;
ALTER DATABASE ai_interviewer_db OWNER TO ai_interviewer_user;
ALTER ROLE ai_interviewer_user CREATEDB;
