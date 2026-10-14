FROM ghcr.io/astral-sh/uv:0.11.15 AS uv
FROM python:3.13.14-slim-trixie AS build
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock /app/
COPY services/platform /app/services/platform
RUN uv sync --locked --no-dev --no-editable --package open-cycling-workshop-platform

FROM python:3.13.14-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 ocwp \
    && useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/ocwp ocwp
COPY --from=build /app/.venv /app/.venv
COPY services/platform/alembic.ini /app/services/platform/alembic.ini
COPY services/platform/migrations /app/services/platform/migrations
COPY LICENSE /app/LICENSE
USER ocwp
WORKDIR /app/services/platform
CMD ["uvicorn", "cycling_workshop.runtime:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
