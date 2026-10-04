"""Find the help articles most relevant to a ticket.

Default: TF-IDF, which runs locally, costs nothing and needs no API key.
Optional: Gemini embeddings (RETRIEVER=gemini), which understand meaning better
but use your free embedding quota. Embeddings for the articles are cached on disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .kb import Article


class TfidfRetriever:
    name = "tfidf"

    def __init__(self, articles: list[Article]):
        self.articles = articles
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        docs = [f"{a.title} {a.title} {a.text}" for a in articles]
        self.matrix = self.vec.fit_transform(docs)

    def search(self, query: str, k: int = 3, min_score: float = 0.04) -> list[tuple[Article, float]]:
        scores = cosine_similarity(self.vec.transform([query]), self.matrix)[0]
        order = np.argsort(scores)[::-1][:k]
        return [(self.articles[i], float(scores[i])) for i in order if scores[i] >= min_score]


class GeminiRetriever:
    name = "gemini"

    def __init__(self, articles: list[Article], client, model: str, cache_dir: Path):
        self.articles, self.client, self.model = articles, client, model
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256((model + "".join(a.id + a.text for a in articles)).encode()).hexdigest()[:16]
        cache = cache_dir / f"kb-embeddings-{key}.json"
        if cache.exists():
            self.matrix = np.array(json.loads(cache.read_text()))
        else:
            self.matrix = self._embed([f"{a.title}\n{a.text}" for a in articles], "RETRIEVAL_DOCUMENT")
            cache.write_text(json.dumps(self.matrix.tolist()))

    def _embed(self, texts: list[str], task: str) -> np.ndarray:
        from google.genai import types

        res = self.client.models.embed_content(
            model=self.model, contents=texts, config=types.EmbedContentConfig(task_type=task)
        )
        m = np.array([e.values for e in res.embeddings], dtype=float)
        return m / np.linalg.norm(m, axis=1, keepdims=True)

    def search(self, query: str, k: int = 3, min_score: float = 0.3) -> list[tuple[Article, float]]:
        q = self._embed([query], "RETRIEVAL_QUERY")[0]
        scores = self.matrix @ q
        order = np.argsort(scores)[::-1][:k]
        return [(self.articles[i], float(scores[i])) for i in order if scores[i] >= min_score]
