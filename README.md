YouTube Downloader Telegram Bot

Setup (Docker recommended):
1. Copy files to repo root.
2. Fill .env (or configure env vars in provider).
3. git add/commit/push.
4. Build & run:
   docker build -t yt-tg-bot .
   docker run --env-file .env yt-tg-bot

Local:
1. python -m venv venv && source venv/bin/activate
2. pip install -r requirements.txt
3. export BOT_TOKEN=...; export MONGO_URL=...; export OWNER_ID=...
4. python main.py
