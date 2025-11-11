#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Downloader Bot (Webhook-ready, Koyeb-ready)
- Reacts ONLY to YouTube links (youtube.com / youtu.be)
- Optional cookies support via env YTDLP_COOKIES (path to cookies.txt inside container)
- Exposes health endpoint at /
- Webhook path: /webhook/<BOT_TOKEN>
"""

import os
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.filters import Command
from aiogram.types import InputFile
from yt_dlp import YoutubeDL

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")            # e.g. https://your-app-name.koyeb.app
PORT = int(os.getenv("PORT", "8000"))
YTDLP_COOKIES = os.getenv("YTDLP_COOKIES")  # e.g. /app/cookies.txt (optional)
OWNER_ID = int(os.getenv("OWNER_ID") or 0)  # optional admin id

if not BOT_TOKEN or not APP_URL:
    logger.error("BOT_TOKEN and APP_URL environment variables are required.")
    raise SystemExit("Missing BOT_TOKEN or APP_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- Helpers ----------
def build_ydl_opts():
    opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }
    if YTDLP_COOKIES and os.path.exists(YTDLP_COOKIES):
        opts["cookiefile"] = YTDLP_COOKIES
    return opts

def human_size(bytesize: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if bytesize < 1024.0:
            return f"{bytesize:3.1f}{unit}"
        bytesize /= 1024.0
    return f"{bytesize:.1f}PB"

async def safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# ---------- Commands ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "👋 *YouTube Downloader*\n\n"
        "Send a YouTube video / short / playlist link and I'll download it for you.\n\n"
        "If YouTube requests sign-in for some URLs, upload cookies.txt and set `YTDLP_COOKIES` in env.",
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.reply("Send a YouTube link (video/short/playlist). Other links are ignored.")

# ---------- Main handler: ONLY react to YouTube URLs ----------
@dp.message()
async def handle_message(message: types.Message):
    text = (message.text or "").strip()
    if not text:
        return

    # Ignore non-YouTube messages silently
    if ("youtube.com" not in text) and ("youtu.be" not in text):
        logger.debug("Ignored non-YouTube message from %s", message.from_user.id)
        return

    url = text
    status = await message.reply("📥 Preparing to download...")

    # probe first (detect playlist or auth requirement)
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl_probe:
            info = ydl_probe.extract_info(url, download=False)
    except Exception as e:
        err = str(e)
        logger.warning("Probe failed: %s", err)
        if "sign in" in err.lower() or "use --cookies" in err.lower() or "confirm you're not a bot" in err.lower():
            await status.edit_text(
                "⚠️ This video requires YouTube sign-in. Admin must provide cookies.txt and set `YTDLP_COOKIES`."
            )
            if OWNER_ID:
                try:
                    await bot.send_message(OWNER_ID, f"yt-dlp probe needs cookies for URL: {url}")
                except Exception:
                    pass
            return
        await status.edit_text(f"❌ Failed to read link: {err}")
        return

    ydl_opts = build_ydl_opts()

    def download_single(video_url: str, opts: dict):
        with YoutubeDL(opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info_dict)
            return filename, info_dict

    try:
        # playlist handling
        if info.get("_type") == "playlist" or info.get("entries"):
            entries = info.get("entries") or []
            await status.edit_text(f"📋 Playlist detected: {len(entries)} items. Starting downloads...")
            processed = 0
            for idx, entry in enumerate(entries, start=1):
                entry_url = entry.get("webpage_url") or entry.get("url")
                if not entry_url and entry.get("id"):
                    entry_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                if not entry_url:
                    continue
                await status.edit_text(f"📥 ({idx}/{len(entries)}) downloading...")
                try:
                    filename, infof = await asyncio.get_event_loop().run_in_executor(
                        None, download_single, entry_url, ydl_opts
                    )
                except Exception as e:
                    logger.exception("Entry download failed")
                    await message.reply(f"⚠️ Failed to download entry: {e}")
                    continue
                await send_file_and_cleanup(message, filename, infof)
                processed += 1
            await status.edit_text(f"✅ Playlist finished. {processed}/{len(entries)} processed.")
            return

        # single video
        await status.edit_text("📥 Downloading video...")
        filename, infof = await asyncio.get_event_loop().run_in_executor(
            None, download_single, url, ydl_opts
        )
        await send_file_and_cleanup(message, filename, infof)
        try:
            await status.delete()
        except Exception:
            pass

    except Exception as e:
        err = str(e)
        logger.exception("Download error")
        if "sign in" in err.lower() or "use --cookies" in err.lower():
            await status.edit_text(
                "⚠️ Download blocked: YouTube requests sign-in. Admin: provide cookies.txt and set `YTDLP_COOKIES`."
            )
            if OWNER_ID:
                try:
                    await bot.send_message(OWNER_ID, f"yt-dlp error (cookies required) for URL: {url}")
                except Exception:
                    pass
            return
        await status.edit_text(f"❌ Error while downloading: {err}")

async def send_file_and_cleanup(message: types.Message, filepath: str, info: dict):
    try:
        if not os.path.exists(filepath):
            await message.reply("❌ Download finished but file not found.")
            return
        size = os.path.getsize(filepath)
        title = info.get("title") or os.path.basename(filepath)
        caption = f"🎬 {title} — {human_size(size)}"
        try:
            await message.reply_video(InputFile(filepath), caption=caption)
        except Exception:
            await message.reply_document(InputFile(filepath), caption=caption)
    finally:
        await safe_remove(filepath)

# ---------- Health endpoint & webhook setup ----------
async def health(request):
    return web.Response(text="OK")

async def on_startup(app):
    # log cookies file details for debug (if present)
    try:
        if YTDLP_COOKIES and os.path.exists(YTDLP_COOKIES):
            size = os.path.getsize(YTDLP_COOKIES)
            lines = sum(1 for _ in open(YTDLP_COOKIES, "r", encoding="utf-8", errors="ignore"))
            logger.info("Cookies file present: %s (bytes=%d lines=%d)", YTDLP_COOKIES, size, lines)
        else:
            logger.info("No cookies file found at configured path: %s", YTDLP_COOKIES)
    except Exception as ex:
        logger.warning("Error reading cookies file: %s", ex)

    webhook_url = f"{APP_URL}/webhook/{BOT_TOKEN}"
    try:
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logger.info("Webhook set -> %s", webhook_url)
        if OWNER_ID:
            try:
                await bot.send_message(OWNER_ID, f"✅ Bot started. Webhook set: {webhook_url}")
            except Exception:
                pass
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)

async def on_shutdown(app):
    try:
        await bot.delete_webhook()
        logger.info("Webhook deleted on shutdown.")
    except Exception:
        pass

def run_app():
    app = web.Application()
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=f"/webhook/{BOT_TOKEN}")
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    run_app()
