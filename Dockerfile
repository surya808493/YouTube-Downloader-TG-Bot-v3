# Use official Python image
FROM python:3.13-slim

# metadata
LABEL maintainer="you@example.com"

# avoid buffering for logs
ENV PYTHONUNBUFFERED=1

# install ffmpeg and build deps (ffmpeg needed for merging/transcoding)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/requirements.txt

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application
COPY . /app

# Ensure main.py is executable (optional)
RUN chmod +x /app/main.py || true

# Use a non-root user (optional but recommended)
RUN useradd --create-home botuser || true
USER botuser
WORKDIR /home/botuser

# Copy app into user's home so we have rights
COPY --chown=botuser:botuser . /home/botuser/app
WORKDIR /home/botuser/app

# Default command to run the bot
CMD ["python", "main.py"]
