from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://quotepilot:quotepilot123@localhost:5432/quotepilot"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://quotepilot:quotepilot123@localhost:5432/quotepilot"

    EMBEDDING_DIM: int = 1536
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
