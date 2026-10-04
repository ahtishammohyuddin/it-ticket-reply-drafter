def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["provider"] == "offline" and body["articles"] == 12


def test_draft_returns_three_safe_drafts(client):
    r = client.post("/api/draft", json={"subject": "VPN error 809",
                                        "body": "VPN gives error 809 at home, internet is fine.",
                                        "customer_name": "Bilal Ahmed"})
    assert r.status_code == 200
    data = r.json()
    assert [d["tone"] for d in data["drafts"]] == ["concise", "detailed", "escalation"]
    assert data["analysis"]["category"] == "network_vpn"
    assert data["kb_sources"][0]["id"] == "KB-004"
    assert not any(d["blocked"] for d in data["drafts"])
    assert data["drafts"][0]["body"].startswith("Hi Bilal,")


def test_personal_data_never_reaches_the_drafter_or_log(client, settings):
    r = client.post("/api/draft", json={"subject": "Cannot log in",
                                        "body": "My password is Karachi@2026, email me at a.b@example.com"})
    data = r.json()
    assert "Karachi@2026" not in data["redacted_ticket"] and "example.com" not in data["redacted_ticket"]
    assert data["analysis"]["needs_escalation"] is True
    assert "credentials_shared_in_ticket" in data["signals"]
    log = settings.log_path.read_text()
    assert "Karachi@2026" not in log and "example.com" not in log


def test_security_ticket_is_p1_and_escalated(client):
    data = client.post("/api/draft", json={"subject": "Files encrypted",
                                           "body": "My files are encrypted and there is a ransom note."}).json()
    assert data["analysis"]["priority"] == "P1" and data["analysis"]["needs_escalation"]


def test_validation_rejects_empty_ticket(client):
    assert client.post("/api/draft", json={"subject": "", "body": "x"}).status_code == 422


def test_rate_limit(client):
    payload = {"subject": "Printer", "body": "Printer is not printing anything."}
    codes = [client.post("/api/draft", json=payload).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_check_endpoint_rechecks_edited_drafts(client):
    bad = client.post("/api/check", json={"body": "Please send your password.", "kb_ids": ["KB-001"]}).json()
    assert bad["blocked"] and "asks_for_a_secret" in bad["flags"]
    good = client.post("/api/check", json={"body": "Please use the reset portal.", "kb_ids": ["KB-001"]}).json()
    assert not good["blocked"] and good["flags"] == []
