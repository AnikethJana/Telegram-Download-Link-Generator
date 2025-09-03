FROM python:3.11-bullseye AS builder

WORKDIR /opt/app

# Install build dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim-bullseye
WORKDIR /app

# Create non-root user and set up directories
RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser \
    && mkdir -p /app \
    && chown -R appuser:appuser /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser StreamBot/ ./StreamBot/

# Set environment variables for Python optimization
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# Switch to non-root user
USER appuser

EXPOSE ${PORT}

# Command to run the application
CMD ["python", "-m", "StreamBot"]