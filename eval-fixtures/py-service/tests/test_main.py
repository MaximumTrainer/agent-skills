from app.main import create_activity


def test_create_activity():
    result = create_activity({"payload": "abc"})
    assert result is not None


def test_timeout_is_configured():
    from app.config import REQUEST_TIMEOUT_MS
    assert REQUEST_TIMEOUT_MS > 0
