import pytest

from code_review_bot import CodeReviewBot


def test_review_bot_fails_clearly_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    bot = CodeReviewBot()

    with pytest.raises(ValueError, match="not configured"):
        bot._make_api_request("Review this example")
