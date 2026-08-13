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

    JWT_SECRET_KEY: str = "quotepilot-dev-secret-change-in-production"

    # File storage backend: "local" (default) or "r2"
    STORAGE_BACKEND: str = "local"
    # Optional override for the local upload directory (defaults to <backend>/uploads)
    STORAGE_LOCAL_DIR: str = ""

    # Cloudflare R2 (S3-compatible) settings. Only used when STORAGE_BACKEND=r2.
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
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
