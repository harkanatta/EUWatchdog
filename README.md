# askthispodcast.com — Setup Guide

## What you have

| File         | What it does                                              |
|--------------|-----------------------------------------------------------|
| `schema.sql` | Creates tables + vector index in Supabase                 |
| `ingest.py`  | One-time script: chunks transcripts → embeds → loads DB   |
| `api.py`     | FastAPI backend: receives questions, returns streamed answers |
| `index.html` | Frontend: podcast picker + chat UI                        |

---

## Step 1 — Supabase project

1. Go to https://supabase.com and create a free project
2. In the **SQL Editor**, paste and run `schema.sql`
3. Copy your **Project URL** and **service role key** from Settings → API

---

## Step 2 — Environment variables

Create a `.env` file:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJh...   ← service role key (NOT anon key)
OPENAI_API_KEY=sk-...
```

---

## Step 3 — Transcripts (already done)

`ingest.py` is preconfigured for **EU Watchdog Radio** and reads the 74
transcripts in `eu_watchdog_whisper/transcripts/`. Filenames like

```
20200212_Episode_1_-_Challenging_Public_Investment_Banks.txt
20240627_Warfare_or_welfare_-_the_EU_s_choice.txt   (season 2+, no episode number)
```

are parsed automatically into episode number (when present), publish date,
and a readable title. Run `python test_parse.py` to preview the parsing
without touching any API.

For a future second podcast: point `TRANSCRIPT_DIR` at the new folder,
change `PODCAST_SLUG` / `PODCAST_TITLE` / `PODCAST_DESC`, and re-run.

---

## Step 4 — Run ingestion (one time)

```bash
python -m venv .venv          # already created if you're continuing this setup
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python ingest.py
```

This will:
- Create a podcast row in Supabase
- Create one episode row per transcript file
- Chunk each transcript into ~500-word segments
- Embed each chunk with OpenAI (text-embedding-3-small)
- Store everything in Supabase

**Cost for 70 episodes:** roughly $0.02–0.05 total. Negligible.

---

## Step 5 — Run the backend

```bash
.venv\Scripts\uvicorn api:app --reload
```

Test it (PowerShell):
```powershell
Invoke-RestMethod -Method Post http://localhost:8000/ask `
  -ContentType "application/json" `
  -Body '{"podcast_slug": "eu-watchdog-radio", "question": "What is corporate capture?"}'
```

---

## Step 6 — Open the frontend

Open `index.html` in a browser. It connects to `http://localhost:8000` by default.

When you're ready to go live, change this line in `index.html`:
```js
const API_BASE = "http://localhost:8000";
// → change to your deployed API URL, e.g.:
const API_BASE = "https://your-api.railway.app";
```

---

## Deploying

**Backend (api.py):**
The easiest free option is [Railway](https://railway.app):
1. Push your code to GitHub (`.gitignore` already excludes `.env` and audio files)
2. Connect the repo on Railway — the included `Procfile` and `requirements.txt`
   tell it how to build and start the server
3. Set the three environment variables
4. Deploy — Railway gives you a public URL

**Frontend (index.html):**
Drag and drop the file to [Netlify Drop](https://app.netlify.com/drop).
Or push to GitHub and connect to Netlify for auto-deploys.

---

## Adding a second podcast later

1. Add more transcript files to `transcripts/`, or create a new folder
2. Change `PODCAST_SLUG` and `PODCAST_TITLE` in `ingest.py`
3. Run `python ingest.py` again
4. The new podcast appears automatically in the frontend picker

---

## Cost estimate (running live)

| Service | Free tier | Paid |
|---------|-----------|------|
| Supabase | 500MB storage, plenty for 70–500 eps | $25/mo for more |
| OpenAI embeddings | — | ~$0 at this scale |
| OpenAI chat (gpt-4o-mini) | — | ~$0.002 per question |
| Railway (backend) | $5 free credits/mo | $5/mo |
| Netlify (frontend) | Free | Free |

At 1,000 questions/month your total cost is roughly **$2–3**.
