"""Runtime settings, read from environment variables (or a local .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # "auto" uses Gemini when a key is set, otherwise the offline drafter.
    llm_provider: str = "auto"  # auto | gemini | offline
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    embed_model: str = "gemini-embedding-001"
    retriever: str = "tfidf"  # tfidf (free, local) | gemini (uses embedding quota)
    kb_dir: Path = ROOT / "data" / "kb"
    log_path: Path = ROOT / "logs" / "requests.jsonl"
    rate_limit_per_minute: int = 8
    top_k: int = 3

    @property
    def provider_name(self) -> str:
        if self.llm_provider == "auto":
            return "gemini" if self.gemini_api_key else "offline"
        return self.llm_provider


def load_settings(**overrides) -> Settings:
    env = dict(
        llm_provider=os.getenv("LLM_PROVIDER", "auto").strip().lower(),
        gemini_api_key=(os.getenv("GEMINI_API_KEY") or "").strip() or None,
        gemini_model=os.getenv("GEMINI_MODEL", Settings.gemini_model),
        embed_model=os.getenv("EMBED_MODEL", Settings.embed_model),
        retriever=os.getenv("RETRIEVER", "tfidf").strip().lower(),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "8")),
    )
    env.update(overrides)
    return Settings(**env)
