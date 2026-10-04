from app.config import load_settings
from app.kb import load_articles
from app.retrieval import TfidfRetriever


def test_finds_the_right_article():
    r = TfidfRetriever(load_articles(load_settings().kb_dir))
    cases = {
        "VPN shows error 809 at home": "KB-004",
        "printer queue stuck, nothing prints": "KB-006",
        "I clicked a phishing link": "KB-009",
        "new phone authenticator codes missing": "KB-003",
    }
    for query, expected in cases.items():
        assert expected in [a.id for a, _ in r.search(query, k=3)], query


def test_returns_nothing_for_unrelated_text():
    r = TfidfRetriever(load_articles(load_settings().kb_dir))
    assert r.search("zebra quantum lasagne", k=3) == []
