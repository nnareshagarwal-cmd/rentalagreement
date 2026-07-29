import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    PORT       = int(os.getenv("PORT", 7000))
    SECRET_KEY = os.getenv("SECRET_KEY", "agreement_ai_secret_2026")

    # ── Environment & Debug ────────────────────────────────────────────────
    # IMPORTANT: DEBUG must be False in production.
    # Set FLASK_DEBUG=0 or FLASK_DEBUG=False in your .env for production.
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG     = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    TEMPLATES_AUTO_RELOAD = True

    # ── PostgreSQL ─────────────────────────────────────────────────────────
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres"
    )

    # Connection Pool settings (tune these for your Postgres server limits)
    # Total Postgres connections used = workers × DB_POOL_MAX
    # With 4 Gunicorn workers: 4 × 20 = 80 connections (well under default 100)
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", 2))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", 20))

    # ── AI Provider ────────────────────────────────────────────────────────
    AI_PROVIDER    = os.getenv("AI_PROVIDER", "gemini").lower()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # AWS Bedrock (production AI)
    AWS_REGION      = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_MODEL_ID = os.getenv(
        "BEDROCK_MODEL_ID",
        "anthropic.claude-3-haiku-20240307-v1:0"
    )

    # ── Google Maps (for future address autocomplete integration) ───────────
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # ── Uploads ────────────────────────────────────────────────────────────
    UPLOAD_FOLDER      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size

    # ── Rate Limiting ──────────────────────────────────────────────────────
    # Preview endpoint is rate-limited to prevent DoS
    RATELIMIT_DEFAULT          = "300 per minute"
    RATELIMIT_PREVIEW_ENDPOINT = "30 per second"

    # ── Preview Cache ──────────────────────────────────────────────────────
    PREVIEW_CACHE_SIZE = int(os.getenv("PREVIEW_CACHE_SIZE", 500))  # entries
    PREVIEW_CACHE_TTL  = int(os.getenv("PREVIEW_CACHE_TTL",  10))   # seconds

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
