# EU Watchdog Radio — Episode Downloader
# Requires: yt-dlp  (install: pip install yt-dlp  OR  winget install yt-dlp)
#
# This script downloads all episodes as MP3 files into .\episodes\
# Run it once. Then run 2_transcribe.py to transcribe everything.
#
# Usage (from this folder in PowerShell):
#   .\1_download_episodes.ps1

$RSS_URL = "https://feeds.buzzsprout.com/856474.rss"
$OUT_DIR  = ".\episodes"

if (-not (Test-Path $OUT_DIR)) {
    New-Item -ItemType Directory -Path $OUT_DIR | Out-Null
}

Write-Host "Downloading all EU Watchdog Radio episodes..."
Write-Host "Output folder: $OUT_DIR"
Write-Host ""

# yt-dlp can read RSS feeds directly and download all audio
yt-dlp `
    --extract-audio `
    --audio-format mp3 `
    --audio-quality 0 `
    --output "$OUT_DIR\%(upload_date)s_%(title)s.%(ext)s" `
    --restrict-filenames `
    --no-playlist-reverse `
    --ignore-errors `
    $RSS_URL

Write-Host ""
Write-Host "Done. Episodes saved to: $OUT_DIR"
Write-Host "Now run:  python 2_transcribe.py"
