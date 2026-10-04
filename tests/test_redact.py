from app.redact import redact


def test_removes_personal_data():
    text = "Email jo.smith@example.com, call +92 300 1234567, IP 10.0.0.12, card 4111 1111 1111 1111"
    out, counts = redact(text)
    assert "example.com" not in out and "1234567" not in out and "10.0.0.12" not in out and "4111" not in out
    assert counts == {"EMAIL": 1, "PHONE": 1, "IP": 1, "CARD": 1}


def test_redacts_a_shared_password_but_keeps_the_word():
    out, counts = redact("My password is Karachi@2026 and it fails")
    assert out == "My password is [PASSWORD] and it fails"
    assert counts == {"PASSWORD": 1}


def test_leaves_normal_password_talk_alone():
    for text in ["I need a password reset", "password expired today", "Ticket 12345 about my password: reset please"]:
        out, counts = redact(text)
        assert "[PASSWORD]" not in out, text


def test_ignores_numbers_that_are_not_cards():
    out, counts = redact("Order 1234567890123 is late")
    assert "CARD" not in counts


def test_normal_sentences_about_passwords_are_not_flagged():
    # Regression: a draft saying "your password is incorrect" was blocked as personal data.
    for text in ["It says your password is incorrect.", "Your password is not working yet.",
                 "The password is case sensitive.", "Your password is [PASSWORD]."]:
        out, counts = redact(text)
        assert counts == {}, text


def test_real_looking_passwords_are_still_removed():
    for secret in ["Karachi@2026", "hunter22", "Summer2024!"]:
        out, counts = redact(f"my password is {secret}")
        assert counts == {"PASSWORD": 1} and secret not in out


def test_plain_words_after_password_are_not_secrets():
    # Regression: Gemini drafts like these were blocked as personal data.
    for text in ["Your password is compromised, please change it.",
                 "Choose a new password: Use at least 12 characters.",
                 "Since your password was exposed, reset it now."]:
        out, counts = redact(text)
        assert counts == {}, text
