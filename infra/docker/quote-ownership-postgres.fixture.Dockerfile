# Disposable, non-production fixture; the copied value is explicitly public.
ARG PG_BASE_IMAGE
FROM ${PG_BASE_IMAGE}
ARG SOURCE_TREE
LABEL ocwp.source-tree=$SOURCE_TREE
COPY infra/compose/postgres-init/10-application-role.sql /docker-entrypoint-initdb.d/10-application-role.sql
COPY tests/fixtures/quote-ownership/public-synthetic-password.txt /run/secrets/postgres_password
