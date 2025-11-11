# Use official Python image
FROM python:3.13-slim

LABEL maintainer="you@example.com"

ENV PYTHONUNBUFFERED=1

# Install ffmpeg and minimal deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy application
COPY . /app

RUN chmod +x /app/main.py || true

# Create non-root user
RUN useradd --create-home botuser || true
USER botuser
WORKDIR /home/botuser/app
COPY --chown=botuser:botuser . /home/botuser/app

CMD ["python", "main.py"]
