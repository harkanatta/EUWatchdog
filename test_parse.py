"""Smoke test: run parse_filename over every real transcript filename."""
import os

os.environ.setdefault("OPENAI_API_KEY", "sk-dummy")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "dummy")

from ingest import TRANSCRIPT_DIR, parse_filename

files = sorted(TRANSCRIPT_DIR.glob("*.txt"))
assert files, f"No transcripts found in {TRANSCRIPT_DIR}"

failures = []
for f in files:
    num, date, title = parse_filename(f.name)
    if not title or date is None:
        failures.append(f.name)
    print(f"{str(num or '—'):>3}  {date}  {title}")

print(f"\n{len(files)} files, {len(failures)} parse failures")
if failures:
    print("FAILED:", *failures, sep="\n  ")
    raise SystemExit(1)
