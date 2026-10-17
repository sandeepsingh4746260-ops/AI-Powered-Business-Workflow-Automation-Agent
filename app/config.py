import os
from dotenv import load_dotenv

# Prefer the project-local .env during local Windows development so a stale
# GEMINI_API_KEY left in the terminal cannot silently override the new key.
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip("\"").strip("'")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
SLOW_STEP_THRESHOLD_SECONDS = float(os.getenv("SLOW_STEP_THRESHOLD_SECONDS", "5"))
