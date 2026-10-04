"""Rule-based checks that run before and after the model.
Rules are cheap, testable and never make things up."""
from __future__ import annotations

import re

from .redact import redact

# ---- before the model: signals that a human should look first ----
_SIGNALS = {
    "possible_security_incident": r"phish|ransom|malware|virus|\bhack(ed)?\b|breach|suspicious (link|email|login)|clicked (a|the|on the) link|encrypted|unknown (login|sign-?in)",
    "possible_outage": r"\b(everyone|whole (office|team|floor)|all (users|staff)|nobody (can|in)|entire (office|team))\b|server (is )?down|outage",
    "possible_data_loss": r"\b(deleted|lost|missing)\b.{0,20}\b(files|data|folder|documents)\b|data loss",
    "urgent_language": r"\b(urgent|asap|immediately|emergency|critical)\b",
}

ESCALATE_ON = {
    "possible_security_incident",
    "possible_outage",
    "possible_data_loss",
    "credentials_shared_in_ticket",
}


def ticket_signals(text: str, redaction_counts: dict[str, int]) -> list[str]:
    found = [name for name, pat in _SIGNALS.items() if re.search(pat, text, re.I)]
    if redaction_counts.get("PASSWORD"):
        found.append("credentials_shared_in_ticket")
    return found


# ---- after the model: checks on every draft ----
_ASKS_SECRET = re.compile(
    r"(?i)\b(send|share|provide|tell|give|reply with|confirm|type)\b[^.?!\n]{0,40}\b(password|passcode|mfa code|otp|one[- ]time code|verification code)\b"
)
_NEGATED = re.compile(r"(?i)\b(never|do not|don't|will not|won't|not)\b[^.?!\n]{0,25}$")
_PROMISE = re.compile(
    r"(?i)\b(guarantee[ds]?|refund(ed)?|compensat\w+|will be (fixed|resolved) (by|within|today|tomorrow)|within \d+\s*(minutes?|hours?|days?)|100%)"
)


def _asks_for_secret(body: str) -> bool:
    for m in _ASKS_SECRET.finditer(body):
        before = body[max(0, m.start() - 30):m.start()]
        if not _NEGATED.search(before + m.group(1)) and not _NEGATED.search(before):
            return True
    return False


def check_draft(body: str, cited: list[str], known_ids: set[str]) -> tuple[list[str], bool]:
    """Return (flags, blocked). A blocked draft cannot be approved in the UI."""
    flags: list[str] = []
    blocked = False
    if _asks_for_secret(body):
        flags.append("asks_for_a_secret")
        blocked = True
    if _PROMISE.search(body):
        flags.append("makes_a_promise")
        blocked = True
    _, pii = redact(body)
    if pii:
        flags.append("contains_personal_data:" + ",".join(sorted(pii)))
        blocked = True
    unknown = [c for c in cited if c not in known_ids]
    if unknown:
        flags.append("cites_unknown_article:" + ",".join(unknown))
    if not cited:
        flags.append("no_article_cited")
    return flags, blocked
