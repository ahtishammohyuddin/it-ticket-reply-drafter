"""FastAPI app: JSON API plus the single-page UI."""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Settings, load_settings
from .guardrails import check_draft
from .pipeline import Pipeline, ProviderError
from .ratelimit import RateLimiter
from pydantic import BaseModel, Field

from .schemas import DraftResponse, TicketIn


class CheckIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=6000)
    kb_ids: list[str] = []
    tone: str = "concise"

STATIC = ROOT / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    pipeline = Pipeline(settings)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    samples = json.loads((ROOT / "data" / "samples.json").read_text(encoding="utf-8"))

    app = FastAPI(
        title="IT Ticket Reply Drafter",
        version="1.0.0",
        description="Drafts safe, knowledge-base-grounded replies to IT support tickets for a human agent to review.",
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "provider": pipeline.drafter.name, "model": pipeline.model,
                "retriever": pipeline.retriever.name, "articles": len(pipeline.articles)}

    @app.get("/api/kb")
    def kb():
        return [{"id": a.id, "title": a.title, "category": a.category} for a in pipeline.articles]

    @app.get("/api/samples")
    def get_samples():
        return samples

    @app.post("/api/draft", response_model=DraftResponse)
    def draft(ticket: TicketIn, request: Request):
        client = request.headers.get("x-forwarded-for", request.client.host if request.client else "local").split(",")[0].strip()
        if not limiter.allow(client):
            raise HTTPException(429, "Too many requests. This demo allows a few drafts per minute to stay on the free tier. Try again in a minute.")
        try:
            return pipeline.run(ticket)
        except ProviderError as e:
            print(f"[drafter] {e}", flush=True)  # the real reason, in the server window
            raise HTTPException(503, f"The AI model is unavailable right now ({e.__class__.__name__}). Try again shortly.") from e

    @app.post("/api/check")
    def check(item: CheckIn):
        """Re-run the safety rules on a draft the agent has edited."""
        flags, blocked = check_draft(item.body, item.kb_ids, pipeline.known_ids)
        if item.tone == "escalation":
            flags = [f for f in flags if f != "no_article_cited"]
        return {"flags": flags, "blocked": blocked}

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
