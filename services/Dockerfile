FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/api:/monorepo

# Install uv package manager from official image
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

# Set working directory explicitly to the API project within /app
WORKDIR /app/api

# Dedicated virtual environment outside /app to prevent bind mount collisions
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency manifests for layer caching
COPY services/api/pyproject.toml services/api/uv.lock ./

# Create venv and install dependencies locked
RUN uv venv /opt/venv && \
    VIRTUAL_ENV=/opt/venv uv sync --active --frozen --no-dev

# Copy API application source code and data directory
COPY services/api /app/api
COPY services/data /app/data
COPY data/pipelines /monorepo/data/pipelines
COPY data/__init__.py /monorepo/data/__init__.py
RUN mkdir -p /var/lib/flower

# Setup non-root user appuser (UID 1000 matching host)
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m appuser && \
    chown -R appuser:appuser /app /var/lib/flower

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

