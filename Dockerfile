FROM python:3.11-slim

LABEL maintainer="you@example.com"
ENV PYTHONUNBUFFERED=1

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
COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN chmod +x /app/main.py || true

# create non-root user
RUN useradd --create-home botuser || true
USER botuser
WORKDIR /home/botuser/app
COPY --chown=botuser:botuser . /home/botuser/app

# expose health port (optional)
EXPOSE 8000

CMD ["python", "main.py"]
