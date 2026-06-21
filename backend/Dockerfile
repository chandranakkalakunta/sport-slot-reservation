# ── Builder ──────────────────────────────────────────────────
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src

# Non-editable: project + deps installed into the venv proper
RUN uv sync --frozen --no-dev --no-editable

# ── Runtime ──────────────────────────────────────────────────
FROM python:3.12-slim

RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8080
CMD ["sh", "-c", "uvicorn sport_slot.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
