import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "linkedin-data-api.p.rapidapi.com")

# Playwright behavior
HEADLESS = os.environ.get("HEADLESS", "true").lower() != "false"
PAGE_TIMEOUT_MS = int(os.environ.get("PAGE_TIMEOUT_MS", "20000"))


def require_keys(*names: str) -> None:
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise RuntimeError(
            f"Missing required config value(s): {', '.join(missing)}. "
            "Set them in your .env file (see .env.example)."
        )
