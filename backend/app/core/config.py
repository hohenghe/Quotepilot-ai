from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://quotepilot:quotepilot123@localhost:5432/quotepilot"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://quotepilot:quotepilot123@localhost:5432/quotepilot"

    EMBEDDING_DIM: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()


def is_llm_available() -> bool:
    return bool(settings.OPENAI_API_KEY)
