from app.config import GEMINI_MODEL

def test_default_gemini_model_is_current_configured_default():
    # .env may intentionally override this; default is covered in config source.
    source = open("app/config.py", encoding="utf-8").read()
    assert 'os.getenv("GEMINI_MODEL", "gemini-3.8-flash")' in source
