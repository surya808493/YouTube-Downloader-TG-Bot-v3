# YouTube Downloader Telegram Bot

Features:
- Download YouTube video / short / playlist
- Per-user preferred quality via /setquality (360/480/720/1080/Best)
- Playlist support (sends each video separately)
- Auto-downscale using ffmpeg if file > 2GB
- MongoDB user prefs, /stats and /broadcast for owner

## Requirements
- Python 3.10+
- ffmpeg (for merging/downscaling): install on Ubuntu: `sudo apt update && sudo apt install ffmpeg -y`
- MongoDB connection (Atlas or self-hosted)

## Setup
1. Clone files into a folder.
2. Create `.env` from `.env.example` and fill values.
3. Create virtualenv and install:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
