-- Runs ONCE on an empty PostgreSQL volume. Changing a secret file does not
-- rotate an existing role password. Do not delete a volume to rotate passwords.
\set ON_ERROR_STOP on
-- Do not log expanded credential-bearing statements, including failed ones.
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
\set app_password `cat /run/secrets/postgres_password`
-- A missing/unreadable/short file fails before CREATE ROLE; output is not secret.
SELECT 1 / (length(:'app_password') >= 32)::integer AS valid_secret \gset
CREATE ROLE ocwp LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD :'app_password';
\unset app_password
CREATE DATABASE ocwp OWNER ocwp;
REVOKE ALL ON DATABASE ocwp FROM PUBLIC;
GRANT CONNECT ON DATABASE ocwp TO ocwp;
