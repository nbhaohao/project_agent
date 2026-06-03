# ── Stage 1: install Python deps with uv ─────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy manifests first — layer cache survives source-only changes
COPY pyproject.toml uv.lock ./

# Install production deps into .venv; skip project install (source not here yet)
RUN uv sync --no-dev --frozen --no-install-project

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Pre-built venv from builder — same base image, same Python, so paths match
COPY --from=builder /app/.venv /app/.venv

# Application source (migrate needs migrations/ + alembic.ini too)
COPY app/        ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Activate venv binaries (uvicorn, alembic, python)
ENV PATH="/app/.venv/bin:$PATH"
# Ensure `app` package is importable without an editable install
ENV PYTHONPATH="/app"

# Default: API server. compose overrides command for worker / migrate.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
