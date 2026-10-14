FROM ghcr.io/astral-sh/uv:0.11.15 AS uv
# Keep pg_dump/pg_restore at the same major version as the server. Debian
# trixie's Python is 3.13; generic postgresql-client would instead supply PG17.
FROM postgres:18.4-trixie AS base
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

FROM base AS build
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY services/platform /app/services/platform
RUN uv sync --locked --no-dev --no-editable --package open-cycling-workshop-platform

FROM base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 ocwp \
    && useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/ocwp ocwp
COPY --from=build /app/.venv /app/.venv
COPY pyproject.toml /app/pyproject.toml
COPY services/platform/pyproject.toml services/platform/alembic.ini /app/services/platform/
COPY services/platform/migrations /app/services/platform/migrations
COPY scripts/database /app/scripts/database
COPY LICENSE /app/LICENSE
WORKDIR /app
USER ocwp
ENTRYPOINT ["python", "-m", "scripts.database.backup_postgres"]
CMD ["--help"]
