"""Drafting providers.

GeminiDrafter calls the Gemini API (free tier is enough).
OfflineDrafter needs no key: rules and templates built from the knowledge base.
It keeps the demo and the tests working with zero cost and zero network.
Both return the same JSON shape, so the rest of the app does not care which ran.
"""
from __future__ import annotations

import json
import re
import time

from .kb import Article

CATEGORIES = ["password_login", "access_request", "email", "network_vpn", "hardware", "software", "security", "other"]

SYSTEM = """You are an assistant on an IT service desk. You prepare draft replies that a human agent reviews, edits and sends. You never send anything yourself.

Rules:
- Base every troubleshooting step on the knowledge base articles provided. Cite the article ids you used. If none of them fit, say the team will look into it and ask one specific clarifying question. Do not invent steps, links, system names or policies.
- Never ask the user for a password, PIN, MFA or verification code. If the ticket contains a credential, tell them to change it.
- Never promise timelines, fixes, refunds or outcomes.
- Keep placeholders such as [EMAIL] or [PHONE] exactly as written. Do not try to fill them in.
- Greet the person by first name if a name is given, otherwise "Hi there". Sign off as "IT Service Desk".
- Plain, friendly English. No jargon the user would not know.
- Format each body as an email: the greeting on its own line, a blank line, short paragraphs, numbered steps each on their own line, a blank line, then "Kind regards," and "IT Service Desk" on their own lines.
- Do not write article ids such as [KB-001] in the body. Put them only in kb_ids.

Escalation: set needs_escalation to true only for a security incident, an outage affecting several people, data loss, or a problem first-line steps cannot fix (for example hardware that needs a technician). A missing help article is not a reason to escalate: ask one clarifying question instead. Routine identity checks described in an article (such as a call-back or a temporary access pass) are first-line work, not escalation.

Priority guide: P1 security incident or many people stopped; P2 one person fully blocked; P3 degraded with a workaround; P4 request or question.

Write exactly three drafts:
1. concise: 2 to 4 sentences with the single most likely fix.
2. detailed: numbered steps from the articles, then what to do if they do not work.
3. escalation: acknowledges the issue, says it has been passed to the right team, and lists what information the team will need. Safe to send when the agent cannot solve it.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
        "summary": {"type": "string"},
        "needs_escalation": {"type": "boolean"},
        "escalation_reasons": {"type": "array", "items": {"type": "string"}},
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tone": {"type": "string", "enum": ["concise", "detailed", "escalation"]},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "kb_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["tone", "subject", "body", "kb_ids"],
            },
        },
    },
    "required": ["category", "priority", "summary", "needs_escalation", "escalation_reasons", "drafts"],
}


class ProviderError(RuntimeError):
    """Raised when the model cannot be reached or returns something unusable."""


def build_prompt(subject: str, body: str, name: str | None, articles: list[Article], signals: list[str]) -> str:
    kb = "\n\n".join(f"[{a.id}] {a.title}\n{a.text}" for a in articles) or "(no relevant articles found)"
    return (
        f"KNOWLEDGE BASE ARTICLES:\n{kb}\n\n"
        f"RULE-BASED SIGNALS: {', '.join(signals) or 'none'}\n\n"
        f"CUSTOMER NAME: {name or 'not given'}\n"
        f"TICKET SUBJECT: {subject}\n"
        f"TICKET BODY (personal data already redacted):\n{body}"
    )


class GeminiDrafter:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    def draft(self, subject, body, name, articles, signals) -> dict:
        from google.genai import errors, types

        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0.2,
            response_mime_type="application/json",
            response_json_schema=RESPONSE_SCHEMA,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        prompt = build_prompt(subject, body, name, articles, signals)
        last = None
        for attempt in range(3):
            try:
                res = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
                return json.loads(res.text)
            except errors.APIError as e:
                last = e
                if getattr(e, "code", None) == 429 and attempt < 2:
                    time.sleep(4 * (attempt + 1))  # free tier: back off and retry
                    continue
                break
            except (json.JSONDecodeError, TypeError) as e:
                last = e
        raise ProviderError(f"Gemini call failed: {last}")


# ---------------- offline drafter ----------------

_KEYWORDS = {
    "security": r"phish|suspicious|malware|virus|hack|encrypt|ransom|clicked (a|the|on the) link|unknown (login|sign)",
    "password_login": r"password|locked out|lock(ed)? (me )?out|sign[- ]?in|log ?in|mfa|authenticator|verification code|new phone",
    "network_vpn": r"vpn|wi-?fi|wifi|internet|network|connect",
    "email": r"outlook|email|e-mail|inbox|mailbox",
    "access_request": r"access|permission|shared folder|folder|grant|new starter|onboard",
    "software": r"install|software|licen[cs]e|app(lication)? request",
    "hardware": r"printer|print|laptop|slow|screen|keyboard|mouse|monitor",
}


class OfflineDrafter:
    """Rules and templates. Clearly labelled in the UI as 'Offline mode (no AI)'."""

    name = "offline"

    def draft(self, subject, body, name, articles, signals) -> dict:
        text = f"{subject} {body}".lower()
        category = "other"
        for cat, pat in _KEYWORDS.items():
            if re.search(pat, text):
                category = cat
                break
        if articles and category == "other":
            category = articles[0].category
        escalate_reasons = [s for s in signals if s != "urgent_language"]
        if "possible_security_incident" in signals or "possible_outage" in signals:
            priority = "P1"
        elif re.search(r"can'?t (work|log|sign|access)|cannot (work|log|sign|access)|locked out|blocked", text):
            priority = "P2"
        elif category in ("access_request", "software"):
            priority = "P4"
        else:
            priority = "P3"
        greet = f"Hi {name.split()[0]}," if name else "Hi there,"
        top = articles[0] if articles else None
        ids = [top.id] if top else []
        sign = "\n\nKind regards,\nIT Service Desk"
        cred = "\n\nYou included a password in your message. Please change it now, and never share it with anyone, including us." if "credentials_shared_in_ticket" in signals else ""
        if top and top.steps:
            first = top.steps[0].rstrip(".")
            concise = f"{greet}\n\nThanks for getting in touch. Our guide \"{top.title}\" covers this. Start with this step: {first[0].lower() + first[1:]}. If that does not help, reply here and we will take it further.{cred}{sign}"
            steps = "\n".join(f"{i}. {s}" for i, s in enumerate(top.steps, 1))
            detailed = f"{greet}\n\nThanks for reporting this. Please try these steps from our guide \"{top.title}\":\n\n{steps}\n\nIf the problem continues after these steps, reply to this ticket with what you tried and any error message you see.{cred}{sign}"
        else:
            concise = f"{greet}\n\nThanks for getting in touch. We are looking into this. Could you tell us exactly what you see on screen, including any error message?{cred}{sign}"
            detailed = concise
        escalation = (
            f"{greet}\n\nThanks for reporting this. I have passed your ticket to the right team so they can look into it properly."
            f"\n\nTo help them, please reply with:\n- when the problem started\n- any error message, exactly as shown\n- whether anyone else is affected{cred}{sign}"
        )
        subj = f"Re: {subject}"
        return {
            "category": category,
            "priority": priority,
            "summary": (subject.strip()[:140]),
            "needs_escalation": bool(escalate_reasons),
            "escalation_reasons": escalate_reasons,
            "drafts": [
                {"tone": "concise", "subject": subj, "body": concise, "kb_ids": ids},
                {"tone": "detailed", "subject": subj, "body": detailed, "kb_ids": ids},
                {"tone": "escalation", "subject": subj, "body": escalation, "kb_ids": []},
            ],
        }
