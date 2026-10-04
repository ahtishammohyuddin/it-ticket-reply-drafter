# Evaluation results (2026-10-05)

Provider: `gemini` · model: `gemini-3.5-flash-lite` · retriever: `tfidf` · tickets: 30

| Metric | Result |
|---|---|
| Category accuracy | 26/30 (87%) |
| Right article in top 3 | 25/27 (93%) |
| Escalation recall (caught real escalations) | 8/8 (100%) |
| Escalation precision (escalations that were real) | 8/11 (73%) |
| Drafts blocked by guardrails | 0/90 |

## Misses

- T02 escalated but should not have
- T03 category: expected password_login, got security
- T03 escalated but should not have
- T10 retrieval: KB-008 not in top 3
- T19 category: expected other, got software
- T20 category: expected other, got software
- T24 retrieval: KB-009 not in top 3
- T25 escalated but should not have
- T29 category: expected software, got access_request
