YouTube Downloader Bot (Webhook + cookies support)

1) Export cookies.txt from your logged-in browser if you need to download restricted videos.
2) Upload cookies.txt as a secret/file to your provider and set YTDLP_COOKIES to its path (e.g. /app/cookies.txt).
3) Set environment variables: BOT_TOKEN, APP_URL (https://...), PORT=8000, optional OWNER_ID.
4) Deploy Docker (or use provider's build). The app exposes health at / and webhook at /webhook/<BOT_TOKEN>.
5) Send a YouTube URL to the bot in Telegram.
