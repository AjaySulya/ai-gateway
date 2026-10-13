FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't reinstall everything.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync

# Render sets PORT; elsewhere it falls back to 8000.
# Migrations run on every start, which is safe: upgrade head does nothing when up to date.
CMD ["sh", "-c", "alembic upgrade head && uvicorn gateway.main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
