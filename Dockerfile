FROM python:3.11-slim

ARG VERSION=dev
ENV VERSION=${VERSION}
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* ./

RUN pip install --no-cache-dir poetry \
 && poetry config virtualenvs.create false \
 && poetry install --only main --no-interaction --no-ansi

COPY inception_reports ./inception_reports
COPY scripts ./scripts

ENTRYPOINT ["inception_reports"]
