YouTube Downloader Telegram Bot — ready

Requirements:
- Docker (recommended) or Python 3.12+ locally
- MongoDB (Atlas or self-hosted)
- Telegram BOT_TOKEN, OWNER_ID, MONGO_URL in env

Local run:
1. python -m venv venv
2. source venv/bin/activate
3. pip install -r requirements.txt
4. export BOT_TOKEN=...
   export MONGO_URL=...
   export OWNER_ID=...
5. python main.py

Docker:
1. docker build -t yt-tg-bot .
2. docker run --env-file .env yt-tg-bot

Notes:
- ffmpeg required for merging/downscaling (Dockerfile installs it)
- Files > 2GB will be auto-downscaled (ffmpeg) if possible
- For heavy use, ensure sufficient disk & CPU
