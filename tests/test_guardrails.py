from app.guardrails import check_draft, ticket_signals

IDS = {"KB-001", "KB-009"}


def test_blocks_asking_for_a_password():
    flags, blocked = check_draft("Please reply with your password and we will check it.", ["KB-001"], IDS)
    assert "asks_for_a_secret" in flags and blocked


def test_allows_warning_not_to_share_a_password():
    flags, blocked = check_draft("Please never share your password with anyone, including us.", ["KB-001"], IDS)
    assert not blocked and flags == []


def test_blocks_promises():
    for body in ["This will be fixed within 2 hours.", "We guarantee it works now.", "You will get a refund."]:
        flags, blocked = check_draft(body, ["KB-001"], IDS)
        assert "makes_a_promise" in flags and blocked, body


def test_blocks_personal_data_in_a_draft():
    flags, blocked = check_draft("Call me on +92 300 1234567.", ["KB-001"], IDS)
    assert "contains_personal_data:PHONE" in flags and blocked


def test_flags_made_up_article_ids():
    flags, blocked = check_draft("See our guide.", ["KB-999"], IDS)
    assert any(f.startswith("cites_unknown_article") for f in flags)


def test_security_and_outage_signals():
    assert "possible_security_incident" in ticket_signals("I clicked a link in a strange email", {})
    assert "possible_outage" in ticket_signals("Nobody can print, the whole team is stuck", {})
    assert "credentials_shared_in_ticket" in ticket_signals("cannot log in", {"PASSWORD": 1})
    assert ticket_signals("My printer is out of toner", {}) == []
