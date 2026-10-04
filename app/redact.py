"""Remove personal data before a ticket goes anywhere near a model or a log."""
from __future__ import annotations

import re
from collections import Counter

# Words that often follow "password is" in normal sentences and are not passwords.
_NOT_A_SECRET = (
    r"reset|expired?|change[ds]?|policy|incorrect|wrong|invalid|correct|not|no|now|still|being|too|"
    r"the|a|an|at|required|working|case|saved|stored|shared|sent|different|new|old|current|temporary|longer"
)
_PASSWORD = re.compile(
    r"(?i)\b(password|passwd|pwd|passcode)\b(\s*(?:is|was|=|:)\s*)"
    r"(?!\[)(?!(?:" + _NOT_A_SECRET + r")\b)(\S{3,})"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d ().-]{7,}\d(?![\w-])")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, counts_by_type). Specific patterns run before general ones."""
    counts: Counter[str] = Counter()

    def password(m: re.Match) -> str:
        value = m.group(3).rstrip(".,;:!?)'\"")
        # Only treat it as a password if it looks like one: a digit or a symbol.
        # Plain words ("compromised", "must") are normal sentences, not secrets.
        if not re.search(r"[\d\W_]", value):
            return m.group(0)
        counts["PASSWORD"] += 1
        return m.group(1) + m.group(2) + "[PASSWORD]"

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            counts["CARD"] += 1
            return "[CARD]"
        return m.group(0)

    def simple(label: str):
        def f(m: re.Match) -> str:
            counts[label] += 1
            return f"[{label}]"
        return f

    def phone(m: re.Match) -> str:
        if len(re.sub(r"\D", "", m.group(0))) >= 9:
            counts["PHONE"] += 1
            return "[PHONE]"
        return m.group(0)

    out = _PASSWORD.sub(password, text)
    out = _EMAIL.sub(simple("EMAIL"), out)
    out = _CARD.sub(card, out)
    out = _IPV4.sub(simple("IP"), out)
    out = _PHONE.sub(phone, out)
    return out, dict(counts)
