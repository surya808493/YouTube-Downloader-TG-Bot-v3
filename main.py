import os
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.filters import Command
from aiogram.types import InputFile
from yt_dlp import YoutubeDL

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # e.g., https://your-app-name.koyeb.app
PORT = int(os.getenv("PORT", "8000"))

if not BOT_TOKEN or not APP_URL:
    raise ValueError("❌ BOT_TOKEN and APP_URL environment variables are required!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# -------------------- Command Handlers --------------------
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 *Welcome to YouTube Downloader Bot!*\n\n"
        "Send any YouTube video, short, or playlist link to download.",
        parse_mode="Markdown"
    )


# -------------------- Download Handler --------------------
@dp.message()
async def download_youtube(message: types.Message):
    url = message.text.strip()
    if not ("youtube.com" in url or "youtu.be" in url):
        return await message.reply("❌ Please send a valid YouTube link!")

    status = await message.reply("📥 Downloading your video... Please wait!")

    try:
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "merge_output_format": "mp4",
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        await message.reply_video(InputFile(filename), caption=f"🎬 {info.get('title', 'Video')}")
        os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")
        logger.error(f"Download error: {e}")


# -------------------- Webhook & Health Server --------------------
async def health(request):
    return web.Response(text="OK")

async def on_startup(app):
    webhook_url = f"{APP_URL}/webhook/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logger.info(f"✅ Webhook set: {webhook_url}")

async def on_shutdown(app):
    await bot.delete_webhook()
    logger.info("🧹 Webhook deleted.")

def main():
    app = web.Application()
    app.router.add_get("/", health)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/webhook/{BOT_TOKEN}")
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
