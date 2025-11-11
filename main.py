import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InputFile
from yt_dlp import YoutubeDL
from aiohttp import web

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "8000"))
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ------------------- Command Handlers -------------------
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    await msg.answer(
        "👋 *Welcome to YouTube Downloader Bot!*\n\n"
        "Send any YouTube video, short, or playlist link to download it.",
        parse_mode="Markdown",
    )


# ------------------- Download Handler -------------------
@dp.message()
async def downloader(msg: types.Message):
    url = msg.text.strip()
    if not ("youtube.com" in url or "youtu.be" in url):
        return await msg.reply("❌ Please send a valid YouTube link!")

    status = await msg.reply("📥 Downloading your video... Please wait!")

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

        await msg.reply_video(InputFile(filename), caption=f"🎬 {info.get('title', 'Downloaded Video')}")
        os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")
        logger.error(f"Download error: {e}")


# ------------------- Health Check Server -------------------
async def health(request):
    return web.Response(text="OK")

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ Health server running on port {PORT}")
    while True:
        await asyncio.sleep(3600)


# ------------------- Main -------------------
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Webhook deletion failed: {e}")

    asyncio.create_task(start_health_server())
    logger.info("🚀 Bot started polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
