"""Load the knowledge base: one Markdown file per article."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    category: str
    text: str

    @property
    def steps(self) -> list[str]:
        return [ln.split(". ", 1)[1] for ln in self.text.splitlines() if ln[:2].rstrip(".").isdigit() and ". " in ln]


def load_articles(kb_dir: Path) -> list[Article]:
    articles = []
    for path in sorted(kb_dir.glob("*.md")):
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        title = lines[0].lstrip("# ").strip()
        category = "other"
        body = lines[1:]
        if body and body[0].lower().startswith("category:"):
            category = body[0].split(":", 1)[1].strip()
            body = body[1:]
        articles.append(Article(id=path.stem, title=title, category=category, text="\n".join(body).strip()))
    if not articles:
        raise RuntimeError(f"No knowledge base articles found in {kb_dir}")
    return articles
