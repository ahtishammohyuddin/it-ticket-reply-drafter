"""Score the drafter on 30 made-up tickets with known answers.

Usage:
    python -m eval.run_eval                 # uses your .env (Gemini if a key is set)
    LLM_PROVIDER=offline python -m eval.run_eval

Writes eval/results.md. Free-tier tip: the script waits between calls so it stays
under the per-minute limit. Set EVAL_DELAY_SECONDS=0 for offline runs.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date

from app.config import ROOT, load_settings
from app.pipeline import Pipeline
from app.schemas import TicketIn


def main() -> None:
    settings = load_settings()
    pipe = Pipeline(settings)
    delay = float(os.getenv("EVAL_DELAY_SECONDS", "0" if settings.provider_name == "offline" else "7"))
    rows = [json.loads(line) for line in (ROOT / "data" / "eval" / "tickets.jsonl").read_text().splitlines() if line.strip()]

    cat_ok = kb_ok = kb_total = 0
    tp = fp = fn = 0
    blocked = drafts = 0
    misses = []
    for i, r in enumerate(rows):
        res = pipe.run(TicketIn(subject=r["subject"], body=r["body"], customer_name=r["customer_name"]))
        a = res.analysis
        if a.category.value == r["expected_category"]:
            cat_ok += 1
        else:
            misses.append(f"{r['id']} category: expected {r['expected_category']}, got {a.category.value}")
        if r["expected_kb"]:
            kb_total += 1
            if r["expected_kb"] in [k.id for k in res.kb_sources]:
                kb_ok += 1
            else:
                misses.append(f"{r['id']} retrieval: {r['expected_kb']} not in top {settings.top_k}")
        if a.needs_escalation and r["expected_escalation"]:
            tp += 1
        elif a.needs_escalation:
            fp += 1
            misses.append(f"{r['id']} escalated but should not have")
        elif r["expected_escalation"]:
            fn += 1
            misses.append(f"{r['id']} missed an escalation")
        drafts += len(res.drafts)
        blocked += sum(d.blocked for d in res.drafts)
        if delay and i < len(rows) - 1:
            time.sleep(delay)

    n = len(rows)
    recall = tp / (tp + fn) if tp + fn else 1.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    lines = [
        f"# Evaluation results ({date.today().isoformat()})",
        "",
        f"Provider: `{pipe.drafter.name}` · model: `{pipe.model}` · retriever: `{pipe.retriever.name}` · tickets: {n}",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Category accuracy | {cat_ok}/{n} ({cat_ok / n:.0%}) |",
        f"| Right article in top {settings.top_k} | {kb_ok}/{kb_total} ({kb_ok / kb_total:.0%}) |",
        f"| Escalation recall (caught real escalations) | {tp}/{tp + fn} ({recall:.0%}) |",
        f"| Escalation precision (escalations that were real) | {tp}/{tp + fp} ({precision:.0%}) |",
        f"| Drafts blocked by guardrails | {blocked}/{drafts} |",
        "",
        "## Misses",
        "",
        *(f"- {m}" for m in misses or ["None"]),
        "",
    ]
    out = ROOT / "eval" / "results.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
