"""
ingest.py — One-time script to chunk transcripts and load into Supabase
─────────────────────────────────────────────────────────────────────────
Usage:
  pip install supabase openai tiktoken python-dotenv

  Set these in a .env file:
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY=your-service-role-key   # NOT the anon key
    OPENAI_API_KEY=your-openai-key

  Then run:
    python ingest.py

Transcript filenames are expected to start with a date, optionally followed
by an episode number (the Whisper pipeline's naming):
  20200212_Episode_1_-_Challenging_Public_Investment_Banks.txt
  20240627_Warfare_or_welfare_-_the_EU_s_choice.txt        (no episode number)

Each .txt file is one episode's full transcript as plain text.
"""

import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

TRANSCRIPT_DIR   = Path(__file__).parent / "eu_watchdog_whisper" / "transcripts"
CHUNK_SIZE       = 500        # target words per chunk
CHUNK_OVERLAP    = 50         # words of overlap between chunks
EMBEDDING_MODEL  = "text-embedding-3-small"   # 1536 dims, cheap, good quality
EMBED_BATCH_SIZE = 20         # embed N chunks per API call

PODCAST_SLUG     = "eu-watchdog-radio"
PODCAST_TITLE    = "EU Watchdog Radio"
PODCAST_DESC     = ("A podcast about corporate lobbying and public money in the EU, "
                    "by Corporate Europe Observatory and Counter Balance.")

# ── Clients ───────────────────────────────────────────────────────────────────

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase      = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"]
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping word-window chunks."""
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a batch of texts."""
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


# Filename: YYYYMMDD_[Episode_N_]Title_with_underscores
FILENAME_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})_(?:Episode_(\d+)_)?(.+)$")


def prettify_title(raw: str) -> str:
    """Turn 'the_EU_s_deregulation_frenzy_-_what_s_at_stake' into readable text.
    Casing is kept as-is (filenames already carry it; .title() would mangle 'EU')."""
    raw = re.sub(r"^[-_\s]+", "", raw)
    raw = re.sub(r"_s(_|$)", r"'s\1", raw)   # possessive apostrophes lost in filenames
    raw = raw.replace("_", " ")
    return re.sub(r"\s+", " ", raw).strip()


def parse_filename(filename: str) -> tuple[int | None, str | None, str]:
    """Return (episode_number, published_at ISO date, title) from a filename."""
    stem = Path(filename).stem
    match = FILENAME_RE.match(stem)
    if not match:
        return None, None, prettify_title(stem)
    yyyy, mm, dd, ep_num, rest = match.groups()
    published = f"{yyyy}-{mm}-{dd}"
    return (int(ep_num) if ep_num else None), published, prettify_title(rest)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Upsert podcast row
    print(f"Upserting podcast: {PODCAST_TITLE}")
    podcast_resp = supabase.table("podcasts").upsert({
        "slug":        PODCAST_SLUG,
        "title":       PODCAST_TITLE,
        "description": PODCAST_DESC,
    }, on_conflict="slug").execute()

    podcast_id = podcast_resp.data[0]["id"]
    print(f"  podcast_id = {podcast_id}")

    # 2. Process each transcript file
    transcript_files = sorted(TRANSCRIPT_DIR.glob("*.txt"))
    if not transcript_files:
        print(f"No .txt files found in {TRANSCRIPT_DIR}/")
        return

    for filepath in transcript_files:
        ep_number, published_at, ep_title = parse_filename(filepath.name)
        ep_label = f"Ep {ep_number}: " if ep_number else ""
        print(f"\nProcessing: {filepath.name}  →  {ep_label}{ep_title}")

        # Insert episode row (source_file is the stable identity for re-runs)
        ep_resp = supabase.table("episodes").upsert({
            "podcast_id":      podcast_id,
            "episode_number":  ep_number,
            "title":           ep_title,
            "published_at":    published_at,
            "source_file":     filepath.name,
        }, on_conflict="podcast_id,source_file").execute()

        episode_id = ep_resp.data[0]["id"]

        # Read and chunk the transcript
        text   = filepath.read_text(encoding="utf-8")
        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        print(f"  {len(text.split())} words → {len(chunks)} chunks")

        # Delete existing chunks for this episode (safe re-run)
        supabase.table("chunks")\
            .delete()\
            .eq("episode_id", episode_id)\
            .execute()

        # Embed and insert in batches
        all_rows = []
        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch_texts = chunks[i : i + EMBED_BATCH_SIZE]
            embeddings  = embed_batch(batch_texts)

            for j, (content, embedding) in enumerate(zip(batch_texts, embeddings)):
                all_rows.append({
                    "podcast_id":  podcast_id,
                    "episode_id":  episode_id,
                    "chunk_index": i + j,
                    "content":     content,
                    "embedding":   embedding,
                })

            print(f"  Embedded chunks {i}–{i + len(batch_texts) - 1}")
            time.sleep(0.2)   # gentle rate limiting

        # Bulk insert
        supabase.table("chunks").insert(all_rows).execute()
        print(f"  ✓ Inserted {len(all_rows)} chunks")

    print("\n✓ Ingestion complete.")


if __name__ == "__main__":
    main()
