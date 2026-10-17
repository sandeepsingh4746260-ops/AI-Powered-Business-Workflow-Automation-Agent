from app.llm import _friendly_api_error, GeminiUnavailable

def test_suspended_consumer_has_actionable_error_without_echoing_key():
    err = _friendly_api_error(Exception("403 PERMISSION_DENIED: CONSUMER_SUSPENDED api_key:secret123"))
    assert isinstance(err, GeminiUnavailable)
    assert "project is SUSPENDED" in str(err)
    assert "secret123" not in str(err)
    assert "different active project" in str(err)

def test_quota_error_is_actionable():
    err = _friendly_api_error(Exception("RESOURCE_EXHAUSTED quota exceeded"))
    assert "quota" in str(err).lower()

def test_invalid_key_error_is_actionable():
    err = _friendly_api_error(Exception("API_KEY_INVALID"))
    assert "API key" in str(err)
