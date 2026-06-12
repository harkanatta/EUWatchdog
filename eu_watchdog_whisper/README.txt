EU WATCHDOG RADIO — DOWNLOAD + TRANSCRIBE ALL EPISODES
=======================================================

STEP 1: Install tools (once)
-----------------------------
In PowerShell (or any terminal):

    pip install yt-dlp openai-whisper

yt-dlp downloads the episodes.
openai-whisper transcribes them.

First whisper run also downloads the model (~1.5 GB for 'medium') — cached after that.


STEP 2: Download all episodes
------------------------------
In PowerShell, from this folder:

    .\1_download_episodes.ps1

This reads the Buzzsprout RSS feed and downloads all ~60 episodes as MP3
into an 'episodes' subfolder. Takes a few minutes depending on your connection.


STEP 3: Transcribe everything
------------------------------

    python 2_transcribe.py

Processes every MP3 in 'episodes', saves one .txt per episode into 'transcripts'.
Already-done files are skipped, so you can re-run safely after interruptions.

Model options (tradeoff: speed vs accuracy):
    python 2_transcribe.py --model tiny     # fastest, ~1-2 min/episode on CPU
    python 2_transcribe.py --model small    # good balance
    python 2_transcribe.py --model medium   # recommended (default)
    python 2_transcribe.py --model large    # best quality, slowest

On a modern laptop CPU, medium does ~45-min episode in ~5-10 minutes.
In your Docker/RStudio environment, performance depends on whether you have GPU access.


RUNNING IN DOCKER (your grodur image or similar)
-------------------------------------------------
If you want to run this inside Docker instead of Windows:

    docker exec -it <container> bash
    pip install yt-dlp openai-whisper
    yt-dlp --extract-audio --audio-format mp3 \
        -o "/data/episodes/%(upload_date)s_%(title)s.%(ext)s" \
        "https://feeds.buzzsprout.com/856474.rss"
    python 2_transcribe.py --episodes /data/episodes --out /data/transcripts


FILES
-----
  1_download_episodes.ps1   PowerShell script — download all episodes via yt-dlp
  2_transcribe.py           Python script — transcribe all MP3s with Whisper
  README.txt                This file
  
  episodes/                 Created by step 2 — MP3 files
  transcripts/              Created by step 3 — TXT transcripts
