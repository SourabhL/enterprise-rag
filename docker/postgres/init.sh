#!/bin/bash
# Runs once, as the POSTGRES_USER bootstrap superuser, on first container init.
# Creates a separate, non-superuser application role. RLS is *always* bypassed for
# superusers (even with FORCE ROW LEVEL SECURITY on a table), so the app and worker
# must never connect as the POSTGRES_USER bootstrap/migrator role -- only as this
# restricted role -- or the tenant-isolation RLS policies become a silent no-op.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";

    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rag_app') THEN
        CREATE ROLE rag_app LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
      END IF;
    END
    \$\$;

    GRANT USAGE ON SCHEMA public TO rag_app;
EOSQL
