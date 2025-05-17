FROM python:3.11-bullseye AS builder

WORKDIR /opt/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim-bullseye
WORKDIR /app

RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser

COPY --from=builder /opt/venv /opt/venv

COPY StreamBot/ ./StreamBot/

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080 

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE ${PORT}

# Command to run the application
CMD ["python", "-m", "StreamBot"]