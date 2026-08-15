from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://quotepilot:quotepilot123@localhost:5432/quotepilot"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://quotepilot:quotepilot123@localhost:5432/quotepilot"

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

    JWT_SECRET_KEY: str = "quotepilot-dev-secret-change-in-production"

    # WeChat Mini Program login (jscode2session)
    WECHAT_APPID: str = ""
    WECHAT_APP_SECRET: str = ""

    # Email (Brevo Transactional Email API)
    BREVO_API_KEY: str = ""
    MAIL_FROM_EMAIL: str = "noreply@zhermai.com"
    MAIL_FROM_NAME: str = "QuotePilot"
    FRONTEND_URL: str = "http://localhost:3000"

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


settings = Settings()


def is_llm_available() -> bool:
    return bool(settings.OPENAI_API_KEY)


def is_embedding_available() -> bool:
    key = settings.EMBEDDING_API_KEY or settings.OPENAI_API_KEY
    url = settings.EMBEDDING_BASE_URL or settings.OPENAI_BASE_URL
    return bool(key) and bool(url)
