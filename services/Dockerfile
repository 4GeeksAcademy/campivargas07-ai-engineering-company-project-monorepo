FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/api:/monorepo

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

WORKDIR /app/api
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv venv /opt/venv && \
    VIRTUAL_ENV=/opt/venv uv sync --active --frozen --no-dev

COPY services/api /app/api
COPY services/data /app/data
COPY data /monorepo/data
COPY docs/company-knowledge-base /monorepo/docs/company-knowledge-base

RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m appuser && \
    chown -R appuser:appuser /opt/venv /app /monorepo

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]