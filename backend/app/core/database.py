from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


def _expected_columns() -> dict[str, list[tuple[str, str, str | None]]]:
    return {
        "products": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("name", "TEXT NOT NULL", None),
            ("sku", "TEXT", None),
            ("category", "TEXT DEFAULT 'other'", None),
            ("description", "TEXT", None),
            ("technical_specs", "TEXT", None),
            ("certifications", "TEXT", None),
            ("moq", "INTEGER", None),
            ("unit_price", "NUMERIC", None),
            ("price_range_low", "NUMERIC", None),
            ("price_range_high", "NUMERIC", None),
            ("pricing", "TEXT", None),
            ("lead_time_days", "INTEGER", None),
            ("image_url", "TEXT", None),
            ("is_active", "BOOLEAN DEFAULT TRUE", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
            ("updated_at", "TIMESTAMPTZ", None),
        ],
        "inquiries": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("customer_name", "TEXT", None),
            ("customer_email", "TEXT", None),
            ("customer_company", "TEXT", None),
            ("raw_message", "TEXT NOT NULL", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "inquiry_analyses": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("inquiry_id", "INTEGER NOT NULL", "inquiries(id) ON DELETE CASCADE"),
            ("product_category", "TEXT", None),
            ("quantity", "INTEGER", None),
            ("technical_params", "JSONB DEFAULT '{}'", None),
            ("target_price", "NUMERIC", None),
            ("required_certifications", "JSONB DEFAULT '[]'", None),
            ("delivery_location", "TEXT", None),
            ("delivery_country", "TEXT", None),
            ("missing_info", "JSONB DEFAULT '[]'", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "quotes": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("inquiry_id", "INTEGER", "inquiries(id) ON DELETE CASCADE"),
            ("subject", "TEXT", None),
            ("email_body", "TEXT NOT NULL", None),
            ("matched_products", "JSONB", None),
            ("total_amount_low", "NUMERIC", None),
            ("total_amount_high", "NUMERIC", None),
            ("currency", "TEXT DEFAULT 'USD'", None),
            ("notes", "TEXT", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "documents": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("filename", "TEXT NOT NULL", None),
            ("file_type", "TEXT NOT NULL", None),
            ("file_path", "TEXT NOT NULL", None),
            ("status", "TEXT DEFAULT 'processing'", None),
            ("products_count", "INTEGER DEFAULT 0", None),
            ("error_message", "TEXT", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
    }


async def _sync_columns(conn):
    for table_name, columns in _expected_columns().items():
        result = await conn.execute(
            text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"
            ),
            {"name": table_name},
        )
        table_exists = result.scalar()

        if not table_exists:
            create_cols = []
            for col_name, col_type, fk in columns:
                col_def = f"{col_name} {col_type}"
                if fk:
                    col_def += f" REFERENCES {fk}"
                create_cols.append(col_def)
            sql = f"CREATE TABLE {table_name} (\n  " + ",\n  ".join(create_cols) + "\n)"
            await conn.execute(text(sql))
            logger.info("Created table: %s", table_name)
            continue

        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = :name"
            ),
            {"name": table_name},
        )
        existing = {row[0] for row in result.fetchall()}

        for col_name, col_type, fk in columns:
            if col_name in existing:
                continue
            col_def = f"{col_name} {col_type}"
            if fk:
                col_def += f" REFERENCES {fk}"
            try:
                await conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {col_def}")
                )
                logger.info("Added column %s.%s", table_name, col_name)
            except Exception as e:
                logger.warning("Failed to add column %s.%s: %s", table_name, col_name, e)


async def init_db():
    from app.models.product import Product
    from app.models.document import Document
    from app.models.inquiry import Inquiry, InquiryAnalysis
    from app.models.quote import Quote

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _sync_columns(conn)
