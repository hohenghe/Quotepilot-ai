from pydantic_settings import BaseSettings
from pydantic import model_validator

_DEV_JWT_SECRET = "quotepilot-dev-secret-change-in-production"


class Settings(BaseSettings):
    # "production" enables fail-closed checks (JWT secret, seed gating, CORS).
    # Any other value (incl. unset) is treated as development.
    ENV: str = "development"

    DATABASE_URL: str = "postgresql+asyncpg://quotepilot:quotepilot123@localhost:5432/quotepilot"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://quotepilot:quotepilot123@localhost:5432/quotepilot"

    # Connection pool tuning (prevents stale-connection 500s after DB restarts).
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800

    EMBEDDING_DIM: int = 1024
    EMBEDDING_MODEL: str = "text-embedding-v4"
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BATCH_SIZE: int = 10
    EMBEDDING_MAX_RETRIES: int = 5
    EMBEDDING_TIMEOUT: int = 60

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    # Vision model (multimodal product recognition). Uses the dedicated
    # AI_VISION_* settings when set, otherwise falls back to OPENAI_* / LLM_MODEL.
    AI_VISION_MODEL: str = ""
    AI_VISION_API_KEY: str = ""
    AI_VISION_BASE_URL: str = ""

    # Two-stage product recognition: dedicated OCR model + vision model.
    # Both reuse AI_VISION_API_KEY / AI_VISION_BASE_URL (same provider).
    AI_OCR_MODEL: str = ""
    AI_OCR_TIMEOUT: int = 45
    AI_VISION_TIMEOUT: int = 60
    AI_MAX_IMAGE_DIMENSION: int = 3072
    # JPEG re-encode quality for product-image preprocessing. Lower = smaller
    # payload to the vision/OCR API at the cost of small-character sharpness.
    # 90 is the measured sweet spot (~29% payload cut, negligible text loss).
    PREPROCESS_JPEG_QUALITY: int = 90

    # Dev default is a known constant; production MUST override via env.
    # The @model_validator below fails the boot if ENV=production and the
    # secret is still the default / empty / shorter than 32 bytes.
    JWT_SECRET_KEY: str = _DEV_JWT_SECRET

    # WeChat Mini Program login (jscode2session)
    WECHAT_APPID: str = ""
    WECHAT_APP_SECRET: str = ""

    # Email (Brevo Transactional Email API)
    BREVO_API_KEY: str = ""
    MAIL_FROM_EMAIL: str = "noreply@zhermai.com"
    MAIL_FROM_NAME: str = "QuotePilot"
    FRONTEND_URL: str = "http://localhost:3000"
    # Comma-separated allowed CORS origins (production). e.g.
    # "https://zhermai.com,https://www.zhermai.com". Empty in dev → localhost.
    CORS_ORIGINS: str = ""

    # Admin account provisioning (read from env; no hardcoded production creds).
    # In production, if ADMIN_PASSWORD is unset, admin creation is skipped with a
    # logged warning (fail-safe: no default password is ever used in prod).
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    # Test accounts are NEVER created in production. In dev, set to "true" to opt in.
    CREATE_TEST_ACCOUNTS: str = "false"

    # Anonymous /analyze rate limiting (per-IP, per-60s window).
    ANALYZE_ANON_RATE: int = 5      # guest: 5 req/min/IP
    ANALYZE_USER_RATE: int = 30     # logged-in: 30 req/min/user
    ANALYZE_MAX_CONCURRENCY: int = 8  # global in-flight cap for /analyze

    # File storage backend: "local" (default) or "r2"
    STORAGE_BACKEND: str = "local"
    # Optional override for the local upload directory (defaults to <backend>/uploads)
    STORAGE_LOCAL_DIR: str = ""

    # Cloudflare R2 (S3-compatible) settings.
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_BASE_URL: str = ""
    # Optional overrides (endpoint is normally derived from R2_ACCOUNT_ID)
    R2_ENDPOINT_URL: str = ""
    R2_STORAGE_PREFIX: str = "documents"

    class Config:
        env_file = ".env"
        extra = "allow"

    @model_validator(mode="after")
    def _validate_production_secrets(self):
        """Fail-closed: production must never boot with the dev JWT secret."""
        if self.ENV == "production":
            if (
                not self.JWT_SECRET_KEY
                or self.JWT_SECRET_KEY == _DEV_JWT_SECRET
                or len(self.JWT_SECRET_KEY.encode("utf-8")) < 32
            ):
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a random value of >=32 bytes "
                    "in production (ENV=production). Refusing to start."
                )
        return self


settings = Settings()


def is_production() -> bool:
    return settings.ENV == "production"


def get_cors_origins() -> list[str]:
    """Allowed CORS origins. In production this MUST be explicit; in dev we
    fall back to localhost so local development keeps working."""
    raw = (settings.CORS_ORIGINS or "").strip()
    if raw:
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if is_production():
        origins = set()
        if settings.FRONTEND_URL:
            origins.add(settings.FRONTEND_URL.rstrip("/"))
        # Common production aliases — the operator can override via CORS_ORIGINS.
        origins.update({"https://zhermai.com", "https://www.zhermai.com"})
        return sorted(origins)
    return ["http://localhost:3000"]


def is_llm_available() -> bool:
    return bool(settings.OPENAI_API_KEY)


def is_embedding_available() -> bool:
    key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
    return bool(key) and bool(url)
