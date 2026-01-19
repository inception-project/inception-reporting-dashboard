FROM python:3.11-slim

ARG VERSION=dev
ENV VERSION=${VERSION}
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Native deps needed by numpy / pandas / cryptography stack
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY inception_reports ./inception_reports

# Install the package from source
RUN pip install --no-cache-dir .

ENTRYPOINT ["inception_reports"]
