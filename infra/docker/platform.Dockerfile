FROM ghcr.io/astral-sh/uv:0.11.15 AS uv
FROM python:3.13.14-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY services/platform /app/services/platform
RUN uv pip install --system --no-cache /app/services/platform \
    && useradd --system --uid 10001 --create-home --home-dir /home/ocwp ocwp

USER ocwp
WORKDIR /app/services/platform

CMD ["uvicorn", "cycling_workshop.runtime:app", "--host", "0.0.0.0", "--port", "8000"]
