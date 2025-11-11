#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Video / Shorts / Playlist Downloader Telegram Bot
Features:
- /start, /help, /setquality (360/480/720/1080/Best)
- Downloads via yt-dlp according to user quality preference
- Playlist support: downloads each video and sends separately
- MongoDB (motor) used to store users and their quality preference
- /stats and /broadcast for OWNER only
- 2GB Telegram file size check
- Auto-downscale (ffmpeg) if file > 2GB (tries 1080->720->480->360->240)
Compatible with aiogram v3 (uses dp.start_polling)
"""

import os
import logging
import asyncio
import shutil
import subprocess
from dotenv import load_dotenv

import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
OWNER_ID = int(os.getenv("OWNER_ID") or 0)

if not BOT_TOKEN or not MONGO_URL or not OWNER_ID:
    logger.error("Please set BOT_TOKEN, MONGO_URL and OWNER_ID in your environment.")
    raise SystemExit("Missing environment variables")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)  # works with aiogram v3 in this project style

mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["yt_downloader"]
users_col = db["users"]

# ---------- Helpers: DB ----------
async def add_user(user_id: int):
    doc = await users_col.find_one({"user_id": user_id})
    if not doc:
        await users_col.insert_one({"user_id": user_id, "quality": "best"})

async def set_user_quality(user_id: int, quality: str):
    await users_col.update_one({"user_id": user_id}, {"$set": {"quality": quality}}, upsert=True)

async def get_user_quality(user_id: int) -> str:
    doc = await users_col.find_one({"user_id": user_id})
    if doc and doc.get("quality"):
        return doc["quality"]
    return "best"

async def count_users() -> int:
    return await users_col.count_documents({})

# ---------- Keyboards ----------
def quality_keyboard():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("360p", callback_data="quality_360"),
        InlineKeyboardButton("480p", callback_data="quality_480"),
        InlineKeyboardButton("720p", callback_data="quality_720"),
        InlineKeyboardButton("1080p", callback_data="quality_1080"),
        InlineKeyboardButton("Best", callback_data="quality_best"),
    )
    return kb

# ---------- Utilities ----------
def ytdlp_format_for_quality(quality: str) -> str:
    if quality == "best":
        return "bestvideo+bestaudio/best"
    try:
        h = int(quality)
        if h <= 0:
            return "bestvideo+bestaudio/best"
        return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
    except Exception:
        return "bestvideo+bestaudio/best"

async def cleanup_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"Failed to remove file {path}: {e}")

def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

def run_ffmpeg_transcode(input_path: str, output_path: str, target_height: int) -> bool:
    """
    Re-encode input_path to output_path with target_height.
    Returns True if ffmpeg succeeded (exit code 0); False otherwise.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", f"scale=-2:{target_height}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "24",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        logger.info(f"ffmpeg exit code: {proc.returncode}")
        if proc.returncode == 0 and os.path.exists(output_path):
            return True
        else:
            logger.warning(f"ffmpeg failed: returncode={proc.returncode}")
            logger.debug(proc.stderr.decode(errors="ignore"))
            return False
    except Exception as e:
        logger.exception(f"ffmpeg run error: {e}")
        return False

async def try_downscale_until_under_limit(original_path: str, title: str, max_bytes: int = 2 * 1024 * 1024 * 1024):
    """
    Attempt progressive downscales until file <= max_bytes or targets exhausted.
    Returns path to successful file (original removed), or None if failed.
    """
    try:
        orig_size = os.path.getsize(original_path)
    except Exception as e:
        logger.warning(f"Could not stat {original_path}: {e}")
        return None

    if orig_size <= max_bytes:
        return original_path

    if not is_ffmpeg_available():
        logger.warning("ffmpeg not available for downscale")
        return None

    targets = [1080, 720, 480, 360, 240]
    base_dir = os.path.dirname(original_path) or "."
    name_no_ext = os.path.splitext(os.path.basename(original_path))[0]

    for h in targets:
        tmp_out = os.path.join(base_dir, f"{name_no_ext}_down_{h}.mp4")
        logger.info(f"Attempting transcode to {h}p -> {tmp_out}")
        success = run_ffmpeg_transcode(original_path, tmp_out, h)
        if not success:
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except:
                    pass
            continue
        try:
            new_size = os.path.getsize(tmp_out)
        except:
            new_size = None
        logger.info(f"Result size after {h}p: {new_size}")
        if new_size is not None and new_size <= max_bytes:
            try:
                os.remove(original_path)
            except:
                pass
            return tmp_out
        else:
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except:
                    pass
            continue
    return None

# ---------- Handlers (aiogram decorator style kept from earlier code) ----------
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id)
    txt = (
        "🎬 *YouTube Downloader Bot*\n\n"
        "Send any YouTube link (video / short / playlist) and I'll download it.\n\n"
        "Commands:\n"
        "/setquality - Choose download quality (360/480/720/1080/Best)\n"
        "/help - Show help\n"
        "/stats - Owner only\n"
        "/broadcast - Owner only (reply to a message)\n\n"
        "Note: If a downloaded file > 2GB, I'll try to auto-downscale (ffmpeg) to fit Telegram's 2GB limit."
    )
    await message.reply(txt, parse_mode="Markdown")

@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    txt = (
        "📚 *Help*\n\n"
        "• Send a YouTube link (video / short / playlist).\n"
        "• Use /setquality to set your preferred quality.\n"
        "• Playlist videos are sent one-by-one.\n"
        "• Files larger than 2GB: bot will attempt to downscale automatically (requires ffmpeg).\n"
    )
    await message.reply(txt, parse_mode="Markdown")

@dp.message_handler(commands=["setquality"])
async def cmd_setquality(message: types.Message):
    await add_user(message.from_user.id)
    current = await get_user_quality(message.from_user.id)
    await message.reply(f"Select quality (current: {current})", reply_markup=quality_keyboard())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("quality_"))
async def callback_quality(query: types.CallbackQuery):
    user_id = query.from_user.id
    await add_user(user_id)
    quality = query.data.split("_", 1)[1]
    await set_user_quality(user_id, quality)
    await query.answer(f"Quality set to {quality}", show_alert=False)
    await bot.send_message(user_id, f"✅ Your preferred quality is now *{quality}*", parse_mode="Markdown")

@dp.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ You are not authorized.")
    total = await count_users()
    await message.reply(f"📊 Total users: `{total}`", parse_mode="Markdown")

@dp.message_handler(commands=["broadcast"])
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ You are not authorized.")
    if not message.reply_to_message:
        return await message.reply("Reply to a message (text) that you want to broadcast.")
    body = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not body:
        return await message.reply("Reply to a text message to broadcast.")
    sent = 0
    total = await count_users()
    async for u in users_col.find({}):
        uid = u.get("user_id")
        try:
            await bot.send_message(uid, body)
            sent += 1
        except Exception:
            pass
    await message.reply(f"✅ Broadcast sent to {sent}/{total} users.")

# ---------- Core downloader handler ----------
@dp.message_handler(content_types=["text"])
async def handle_text(message: types.Message):
    url = message.text.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        return await message.reply("❌ Please send a valid YouTube link (video / short / playlist).")

    await add_user(message.from_user.id)
    user_quality = await get_user_quality(message.from_user.id)
    fmt = ytdlp_format_for_quality(user_quality)

    status = await message.reply("📥 Downloading... Please wait (playlist may take long).")

    ydl_opts_common = {
        "outtmpl": "%(title)s.%(ext)s",
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl_probe:
            info = ydl_probe.extract_info(url, download=False)
    except Exception as e:
        logger.exception("Probe failed")
        await status.edit_text(f"❌ Failed to read link: {e}")
        return

    def download_single(video_url: str, opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info_dict)
            return filename, info_dict

    try:
        if info.get("_type") == "playlist" or info.get("entries"):
            entries = info.get("entries") or []
            await status.edit_text(f"📋 Playlist detected. Videos: {len(entries)}. Starting downloads...")
            count = 0
            for entry in entries:
                entry_url = entry.get("webpage_url") or entry.get("url")
                if not entry_url:
                    video_id = entry.get("id")
                    if video_id:
                        entry_url = f"https://www.youtube.com/watch?v={video_id}"
                if not entry_url:
                    continue

                await status.edit_text(f"📥 Downloading ({count+1}/{len(entries)}): {entry.get('title') or entry_url}")
                try:
                    filename, info_dict = await asyncio.get_event_loop().run_in_executor(
                        None, download_single, entry_url, ydl_opts_common
                    )
                except Exception as e:
                    logger.exception(f"Failed to download entry {entry_url}")
                    await message.reply(f"⚠️ Failed to download an entry: {e}")
                    continue

                await process_and_send_file(message, filename, info_dict)
                count += 1

            await status.edit_text(f"✅ Playlist done. {count} videos processed.")
            return

        await status.edit_text("📥 Single video detected. Downloading...")
        try:
            filename, info_dict = await asyncio.get_event_loop().run_in_executor(
                None, download_single, url, ydl_opts_common
            )
        except Exception as e:
            logger.exception("Download failed")
            await status.edit_text(f"❌ Download failed: {e}")
            return

        await process_and_send_file(message, filename, info_dict)
        await status.delete()
    except Exception as e:
        logger.exception("Processing error")
        await status.edit_text(f"❌ Error while processing: {e}")

async def process_and_send_file(message: types.Message, filepath: str, info: dict):
    """
    Handles size checks, auto-downscale if needed, send file, cleanup.
    """
    filepath_to_send = filepath  # default
    try:
        if not os.path.exists(filepath):
            await message.reply("❌ Downloaded file not found.")
            return

        size = os.path.getsize(filepath)
        title = info.get("title") or os.path.basename(filepath)
        max_bytes = 2 * 1024 * 1024 * 1024  # 2GB

        if size > max_bytes:
            await message.reply(f"⚠️ *{title}* is {round(size/1024/1024,2)} MB which is above Telegram's 2GB limit. Attempting to auto-downscale...", parse_mode="Markdown")
            downscaled = await try_downscale_until_under_limit(filepath, title, max_bytes=max_bytes)
            if downscaled:
                filepath_to_send = downscaled
            else:
                await message.reply(f"❌ Could not reduce *{title}* below 2GB. Please try lower /setquality or host externally.", parse_mode="Markdown")
                await cleanup_file(filepath)
                return
        else:
            filepath_to_send = filepath

        final_size = os.path.getsize(filepath_to_send)
        if final_size > max_bytes:
            await message.reply(f"⚠️ File is still too large ({round(final_size/1024/1024,2)} MB). Cannot send via Telegram.", parse_mode="Markdown")
            await cleanup_file(filepath_to_send)
            return

        ext = os.path.splitext(filepath_to_send)[1].lower()
        caption = f"🎬 {title}"
        try:
            if ext in [".mp4", ".mkv", ".webm", ".mov"]:
                await message.reply_video(InputFile(filepath_to_send), caption=caption)
            else:
                await message.reply_document(InputFile(filepath_to_send), caption=caption)
        except Exception:
            await message.reply_document(InputFile(filepath_to_send), caption=caption)
    finally:
        try:
            if os.path.exists(filepath_to_send):
                os.remove(filepath_to_send)
        except Exception:
            pass
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

# ---------- Startup ----------
if __name__ == "__main__":
    logger.info("Starting bot...")
    if not is_ffmpeg_available():
        logger.warning("ffmpeg not found in PATH. Auto-downscale feature will not work. Install ffmpeg for full functionality.")
    # start polling (aiogram v3 compatible)
    asyncio.run(dp.start_polling(bot, skip_updates=True))
