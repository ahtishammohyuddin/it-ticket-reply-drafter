"""The whole flow for one ticket: redact, check, retrieve, draft, check again, log."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from .config import Settings
from .guardrails import ESCALATE_ON, check_draft, ticket_signals
from .kb import load_articles
from .llm import GeminiDrafter, OfflineDrafter, ProviderError
from .redact import redact
from .retrieval import GeminiRetriever, TfidfRetriever
from .schemas import Analysis, Draft, DraftResponse, KBSource, Redaction, TicketIn

__all__ = ["Pipeline", "ProviderError"]


class Pipeline:
    def __init__(self, settings: Settings):
        self.s = settings
        self.articles = load_articles(settings.kb_dir)
        self.known_ids = {a.id for a in self.articles}

        if settings.provider_name == "gemini":
            if not settings.gemini_api_key:
                raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set")
            self.drafter = GeminiDrafter(settings.gemini_api_key, settings.gemini_model)
            self.model = settings.gemini_model
        else:
            self.drafter = OfflineDrafter()
            self.model = "rules-and-templates"

        if settings.retriever == "gemini" and isinstance(self.drafter, GeminiDrafter):
            self.retriever = GeminiRetriever(self.articles, self.drafter.client, settings.embed_model,
                                             settings.log_path.parent / "cache")
        else:
            self.retriever = TfidfRetriever(self.articles)

    def run(self, ticket: TicketIn) -> DraftResponse:
        t0 = time.perf_counter()
        rid = uuid.uuid4().hex[:12]

        subject, s_counts = redact(ticket.subject)
        body, b_counts = redact(ticket.body)
        counts = {k: s_counts.get(k, 0) + b_counts.get(k, 0) for k in set(s_counts) | set(b_counts)}
        signals = ticket_signals(f"{subject}\n{body}", counts)

        hits = self.retriever.search(f"{subject}\n{body}", k=self.s.top_k)
        articles = [a for a, _ in hits]

        raw = self.drafter.draft(subject, body, ticket.customer_name, articles, signals)

        # Rules win over the model: a rule-based escalation signal always escalates.
        reasons = list(dict.fromkeys(list(raw.get("escalation_reasons", [])) + [s for s in signals if s in ESCALATE_ON]))
        needs = bool(raw.get("needs_escalation")) or any(s in ESCALATE_ON for s in signals)
        priority = raw["priority"]
        if "possible_security_incident" in signals and priority not in ("P1",):
            priority = "P1"

        drafts = []
        for d in raw["drafts"][:3]:
            cited = [c for c in d.get("kb_ids", []) if isinstance(c, str)]
            flags, blocked = check_draft(d["body"], cited, self.known_ids)
            if d["tone"] == "escalation":
                flags = [f for f in flags if f != "no_article_cited"]
            drafts.append(Draft(tone=d["tone"], subject=d["subject"], body=d["body"],
                                kb_ids=cited, flags=flags, blocked=blocked))

        resp = DraftResponse(
            request_id=rid,
            analysis=Analysis(category=raw["category"], priority=priority, summary=raw["summary"],
                              needs_escalation=needs, escalation_reasons=reasons),
            drafts=drafts,
            kb_sources=[KBSource(id=a.id, title=a.title, score=round(sc, 3)) for a, sc in hits],
            redactions=[Redaction(type=k, count=v) for k, v in sorted(counts.items())],
            redacted_ticket=f"{subject}\n\n{body}",
            signals=signals,
            provider=self.drafter.name,
            model=self.model,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        self._log(resp)
        return resp

    def _log(self, r: DraftResponse) -> None:
        """Metadata only. No ticket text is written to disk."""
        try:
            self.s.log_path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "request_id": r.request_id,
                "provider": r.provider,
                "model": r.model,
                "category": r.analysis.category.value,
                "priority": r.analysis.priority.value,
                "escalated": r.analysis.needs_escalation,
                "kb": [k.id for k in r.kb_sources],
                "flags": {d.tone.value: d.flags for d in r.drafts},
                "redactions": {x.type: x.count for x in r.redactions},
                "latency_ms": r.latency_ms,
            }
            with self.s.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        except OSError:
            pass  # logging must never break a request
