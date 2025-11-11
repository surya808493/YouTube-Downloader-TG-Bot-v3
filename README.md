# YouTube Downloader Telegram Bot (ready)

## Requirements
- Python 3.13 (Dockerfile uses 3.13-slim)
- ffmpeg (Dockerfile installs it)
- MongoDB connection (Atlas or self-hosted)

## Setup (local)
1. Copy files into a folder.
2. Create `.env` from `.env.example`.
3. Create venv and install:
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
4. Run:
   python main.py

## Docker
Build and run:
  docker build -t yt-tg-bot .
  docker run --env-file .env yt-tg-bot

## Notes
- ffmpeg required for merge/downscale.
- If running on a managed host, set BOT_TOKEN, MONGO_URL, OWNER_ID in provider env settings.
- For heavy playlist usage ensure enough disk & CPU.
