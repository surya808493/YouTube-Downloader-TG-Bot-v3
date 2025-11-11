# Use Python 3.12 slim to ensure wheels for native deps (aiohttp) are available
FROM python:3.12-slim

LABEL maintainer="you@example.com"
ENV PYTHONUNBUFFERED=1

# Install ffmpeg + build tools (needed for some wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       ca-certificates \
       build-essential \
       gcc \
       python3-dev \
       libssl-dev \
       libffi-dev \
       pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements early to cache
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
