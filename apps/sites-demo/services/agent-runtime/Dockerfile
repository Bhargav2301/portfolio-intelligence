FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 runtime \
  && chown -R runtime:runtime /app
USER runtime

EXPOSE 8000
CMD ["sh", "-c", "uvicorn pi_agent_runtime.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]

