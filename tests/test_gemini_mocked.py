"""Exercises the Gemini path with a fake client, so it runs with no key and no network."""
import json
from types import SimpleNamespace

from app.config import load_settings
from app.pipeline import Pipeline
from app.schemas import TicketIn


def fake_reply(body_concise: str):
    return {
        "category": "password_login", "priority": "P2", "summary": "User forgot password",
        "needs_escalation": False, "escalation_reasons": [],
        "drafts": [
            {"tone": "concise", "subject": "Re: Forgot password", "body": body_concise, "kb_ids": ["KB-001"]},
            {"tone": "detailed", "subject": "Re: Forgot password", "body": "Hi Sara,\n\n1. Open the portal.", "kb_ids": ["KB-001"]},
            {"tone": "escalation", "subject": "Re: Forgot password", "body": "Hi Sara,\n\nI have passed this on.", "kb_ids": []},
        ],
    }


def make_pipeline(tmp_path, reply: dict) -> Pipeline:
    s = load_settings(llm_provider="gemini", gemini_api_key="test-key", retriever="tfidf",
                      log_path=tmp_path / "log.jsonl")
    p = Pipeline(s)
    calls = []

    def generate_content(model, contents, config):
        calls.append((model, contents, config))
        return SimpleNamespace(text=json.dumps(reply))

    p.drafter.client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    p.calls = calls
    return p


def test_gemini_path_parses_and_sends_only_redacted_text(tmp_path):
    p = make_pipeline(tmp_path, fake_reply("Hi Sara,\n\nPlease use the reset portal."))
    res = p.run(TicketIn(subject="Forgot password", body="I forgot it. Reach me at sara@example.com", customer_name="Sara Khan"))
    model, prompt, config = p.calls[0]
    assert "sara@example.com" not in prompt and "[EMAIL]" in prompt
    assert "KB-001" in prompt  # the retrieved article is in the prompt
    assert config.response_mime_type == "application/json"
    assert res.provider == "gemini" and res.analysis.category.value == "password_login"
    assert not any(d.blocked for d in res.drafts)


def test_unsafe_model_output_is_blocked(tmp_path):
    p = make_pipeline(tmp_path, fake_reply("Hi Sara, reply with your password and it will be fixed within 1 hour."))
    res = p.run(TicketIn(subject="Forgot password", body="I forgot my password"))
    concise = res.drafts[0]
    assert concise.blocked and "asks_for_a_secret" in concise.flags and "makes_a_promise" in concise.flags


def test_rules_override_the_model_on_security(tmp_path):
    p = make_pipeline(tmp_path, fake_reply("Hi there, please use the portal."))
    res = p.run(TicketIn(subject="Strange email", body="I clicked a link in a phishing email"))
    assert res.analysis.needs_escalation and res.analysis.priority.value == "P1"
