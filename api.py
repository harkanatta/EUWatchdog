"""
api.py — FastAPI backend for EU Watchdog Radio
─────────────────────────────────────────────────
Usage:
  pip install fastapi uvicorn anthropic google-generativeai supabase python-dotenv

  Run locally:
    uvicorn api:app --reload

  Deploy to:
    - Railway (push to GitHub, connect repo)
    - Render (free tier works fine)
    - Vercel (as a serverless function)

  Set environment variables:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    GEMINI_API_KEY
    ANTHROPIC_API_KEY
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from google import genai
from google.genai import types as genai_types
import anthropic
from supabase import create_client

load_dotenv()

app = FastAPI()

# Allow your frontend domain (update before going to production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to ["https://askthispodcast.com"] in prod
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
claude_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
supabase      = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"]
)

EMBEDDING_MODEL = "models/gemini-embedding-001"  # 768 dims (truncated via output_dimensionality)
CHAT_MODEL      = "claude-haiku-4-5-20251001"   # fast, cheap, high quality


# ── Request / Response models ────────────────────────────────────────────────

class AskRequest(BaseModel):
    podcast_slug: str
    question:     str


class PodcastOut(BaseModel):
    id:          str
    slug:        str
    title:       str
    description: str | None


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/podcasts", response_model=list[PodcastOut])
def list_podcasts():
    """Return all available podcasts (for the podcast picker UI)."""
    resp = supabase.table("podcasts")\
        .select("id, slug, title, description")\
        .execute()
    return resp.data


@app.post("/ask")
def ask(req: AskRequest):
    """
    Main RAG endpoint.
    1. Look up podcast_id from slug
    2. Embed the question
    3. Run similarity search in Supabase
    4. Stream an answer from the LLM grounded in the retrieved chunks
    """

    # 1. Resolve podcast (.single() raises on zero rows, so use limit(1) instead)
    podcast_resp = supabase.table("podcasts")\
        .select("id, title")\
        .eq("slug", req.podcast_slug)\
        .limit(1)\
        .execute()

    if not podcast_resp.data:
        raise HTTPException(status_code=404, detail="Podcast not found")

    podcast    = podcast_resp.data[0]
    podcast_id = podcast["id"]

    # 2. Embed the question
    embed_resp = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=req.question,
        config=genai_types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )
    query_embedding = embed_resp.embeddings[0].values

    # 3. Similarity search via the SQL function defined in schema.sql
    match_resp = supabase.rpc("match_chunks", {
        "query_embedding":    query_embedding,
        "filter_podcast_id":  podcast_id,
        "match_count":        8
    }).execute()

    chunks = match_resp.data
    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant content found")

    # 4. Build context string from retrieved chunks
    # Some episodes (teasers, season 2+) have no number — cite by title and date
    context_parts = []
    for chunk in chunks:
        if chunk.get("episode_number") is not None:
            ep_label = f"Episode {chunk['episode_number']}: {chunk['episode_title']}"
        elif chunk.get("published_at"):
            ep_label = f"{chunk['episode_title']} ({chunk['published_at']})"
        else:
            ep_label = chunk["episode_title"]
        context_parts.append(f"[{ep_label}]\n{chunk['content']}")

    context = "\n\n---\n\n".join(context_parts)

    # 5. Compose prompt
    system_prompt = f"""You are a helpful assistant for the podcast "{podcast['title']}".
Answer questions using ONLY the transcript excerpts provided below.
Always cite which episode your answer comes from, e.g. "(Episode 12: Title)".
If the answer isn't in the excerpts, say so honestly — don't make things up.
Be concise and direct."""

    user_prompt = f"""Transcript excerpts:

{context}

---

Question: {req.question}"""

    # 6. Stream the response
    def generate():
        with claude_client.messages.stream(
            model=CHAT_MODEL,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    return StreamingResponse(generate(), media_type="text/plain")
