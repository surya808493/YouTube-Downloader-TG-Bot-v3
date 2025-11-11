YouTube Downloader Telegram Bot (aiogram v3)

1) Fill env (do NOT commit .env to git)
2) Build & run with Docker:
   docker build -t yt-tg-bot .
   docker run --env-file .env -p 8000:8000 yt-tg-bot

3) Deploy on provider (set env BOT_TOKEN, MONGO_URL, OWNER_ID, PORT=8000)
