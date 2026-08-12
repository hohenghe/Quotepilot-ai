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
        "users": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("email", "TEXT NOT NULL UNIQUE", None),
            ("password_hash", "TEXT NOT NULL", None),
            ("role", "TEXT NOT NULL DEFAULT 'seller'", None),
            ("name", "TEXT", None),
            ("country", "TEXT NOT NULL DEFAULT 'CN'", None),
            ("phone", "TEXT", None),
            ("is_active", "BOOLEAN DEFAULT TRUE", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
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
            ("seller_id", "INTEGER", None),
            ("lead_time_days", "INTEGER", None),
            ("image_url", "TEXT", None),
            ("is_active", "BOOLEAN DEFAULT TRUE", None),
            ("embedding", "vector(1024)", None),
            ("embedding_hash", "TEXT", None),
            ("embedding_model", "TEXT", None),
            ("embedding_status", "TEXT DEFAULT 'pending'", None),
            ("embedding_retry_count", "INTEGER DEFAULT 0", None),
            ("embedding_error", "TEXT", None),
            ("embedded_at", "TIMESTAMPTZ", None),
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
        "seller_inquiries": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("inquiry_id", "INTEGER", None),
            ("buyer_id", "INTEGER", None),
            ("seller_id", "INTEGER NOT NULL", None),
            ("product_id", "INTEGER", None),
            ("raw_message", "TEXT NOT NULL", None),
            ("buyer_email", "TEXT", None),
            ("status", "TEXT DEFAULT 'pending'", None),
            ("reply_body", "TEXT", None),
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
    from app.models.user import User
    from app.models.seller_inquiry import SellerInquiry

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await _sync_columns(conn)
        await _migrate_embedding_dimension(conn)
        # Drop unique constraint on sku if it exists (allows duplicate SKUs across sellers)
        try:
            await conn.execute(text(
                "ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key"
            ))
        except Exception:
            pass


async def _migrate_embedding_dimension(conn):
    """Ensure products.embedding column matches settings.EMBEDDING_DIM.
    Existing embeddings (if any) are NULL-safe since generation never succeeded,
    so we drop + recreate with the correct dimension and reset status to pending."""
    try:
        result = await conn.execute(text(
            "SELECT data_type, udt_name FROM information_schema.columns "
            "WHERE table_name = 'products' AND column_name = 'embedding'"
        ))
        row = result.first()
        if not row:
            return

        # Check if column dimension matches settings.EMBEDDING_DIM
        # pgvector stores dimension in information_schema or atttypmod
        dim_result = await conn.execute(text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'products'::regclass AND attname = 'embedding'"
        ))
        dim_row = dim_result.first()
        # atttypmod for vector(n) is n + 4 (pgvector stores dim + 4 in atttypmod)
        if dim_row and dim_row[0] is not None:
            actual_dim = dim_row[0] - 4
            if actual_dim != settings.EMBEDDING_DIM:
                logger.warning(
                    "Embedding dimension mismatch: DB=%s config=%s, migrating...",
                    actual_dim, settings.EMBEDDING_DIM,
                )
                await conn.execute(text("ALTER TABLE products DROP COLUMN embedding"))
                await conn.execute(text(
                    f"ALTER TABLE products ADD COLUMN embedding vector({settings.EMBEDDING_DIM})"
                ))
                await conn.execute(text(
                    "UPDATE products SET embedding_status='pending', embedding_hash=NULL, "
                    "embedding_model=NULL, embedding_retry_count=0, embedding_error=NULL "
                    "WHERE is_active = true"
                ))
                logger.warning("Embedding dimension migrated to %s", settings.EMBEDDING_DIM)
    except Exception as e:
        logger.warning("Embedding dimension migration check failed: %s", e)
