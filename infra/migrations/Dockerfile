FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY services/api/pyproject.toml ./services/api/pyproject.toml
COPY services/api/src ./services/api/src
RUN pip install ./services/api

COPY alembic.ini ./alembic.ini
COPY services/api/alembic ./services/api/alembic
COPY infra/postgres ./infra/postgres
COPY scripts/run_migrations.py ./scripts/run_migrations.py

RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app
CMD ["python", "/app/scripts/run_migrations.py"]
