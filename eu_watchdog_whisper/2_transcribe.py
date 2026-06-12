#!/usr/bin/env python3
"""
EU Watchdog Radio — Batch Transcriber
Uses OpenAI Whisper to transcribe all MP3 files in ./episodes/
and saves .txt transcripts to ./transcripts/

Requirements:
    pip install openai-whisper

The first run downloads the Whisper model (~1.5 GB for 'medium').
Subsequent runs use the cached model.

Usage:
    python 2_transcribe.py
    python 2_transcribe.py --model large    # slower but more accurate
    python 2_transcribe.py --model tiny     # fastest, less accurate
"""

import os
import sys
import argparse
import whisper
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Transcribe EU Watchdog Radio episodes with Whisper")
    parser.add_argument("--model",    default="medium",   help="Whisper model: tiny / base / small / medium / large (default: medium)")
    parser.add_argument("--episodes", default="./episodes",    help="Folder containing MP3 files")
    parser.add_argument("--out",      default="./transcripts", help="Output folder for transcripts")
    parser.add_argument("--language", default="en",       help="Language hint (default: en)")
    args = parser.parse_args()

    episodes_dir   = Path(args.episodes)
    transcripts_dir = Path(args.out)
    transcripts_dir.mkdir(exist_ok=True)

    # Find all audio files
    audio_files = sorted(
        list(episodes_dir.glob("*.mp3")) +
        list(episodes_dir.glob("*.m4a")) +
        list(episodes_dir.glob("*.wav"))
    )

    if not audio_files:
        print(f"No audio files found in {episodes_dir}")
        print("Run 1_download_episodes.ps1 first.")
        sys.exit(1)

    print(f"Found {len(audio_files)} audio files.")
    print(f"Loading Whisper model: {args.model}  (downloads on first run ~1.5 GB for medium)")
    model = whisper.load_model(args.model)
    print(f"Model loaded.\n")

    for i, audio_path in enumerate(audio_files, 1):
        stem = audio_path.stem
        out_path = transcripts_dir / f"{stem}.txt"

        if out_path.exists():
            print(f"[{i:02d}/{len(audio_files)}] SKIP (already done): {stem}")
            continue

        print(f"[{i:02d}/{len(audio_files)}] Transcribing: {audio_path.name} ...", end=" ", flush=True)
        result = model.transcribe(str(audio_path), language=args.language)
        transcript = result["text"].strip()

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {stem}\n\n")
            f.write(f"Source file: {audio_path.name}\n")
            f.write(f"Model: whisper-{args.model}\n\n")
            f.write("---\n\n")
            f.write(transcript)
            f.write("\n")

        words = len(transcript.split())
        print(f"done. ({words} words → {out_path.name})")

    print(f"\nAll done. Transcripts saved to: {transcripts_dir.resolve()}")


if __name__ == "__main__":
    main()
