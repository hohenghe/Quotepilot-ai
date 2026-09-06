from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    connect_args={"timeout": 10},
)
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
            ("email", "TEXT", None),
            ("password_hash", "TEXT", None),
            ("role", "TEXT NOT NULL DEFAULT 'seller'", None),
            ("name", "TEXT", None),
            ("store_name", "TEXT", None),
            ("avatar_url", "TEXT", None),
            ("business_license_url", "TEXT", None),
            ("country", "TEXT NOT NULL DEFAULT 'CN'", None),
            ("phone", "TEXT", None),
            ("uid", "TEXT", None),
            ("email_verified_at", "TIMESTAMPTZ", None),
            ("auth_version", "INTEGER NOT NULL DEFAULT 0", None),
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
            ("images", "JSONB DEFAULT '[]'", None),
            ("is_active", "BOOLEAN DEFAULT TRUE", None),
            ("view_count", "INTEGER DEFAULT 0", None),
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
            ("buyer_id", "INTEGER", "users(id) ON DELETE SET NULL"),
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
        "saved_products": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("user_id", "INTEGER NOT NULL", None),
            ("product_id", "INTEGER NOT NULL", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "reviews": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("seller_id", "INTEGER NOT NULL", None),
            ("user_id", "INTEGER NOT NULL", None),
            ("rating", "DOUBLE PRECISION NOT NULL", None),
            ("content", "TEXT", None),
            ("images", "JSONB DEFAULT '[]'", None),
            ("reported", "BOOLEAN DEFAULT FALSE", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "auth_tokens": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("user_id", "INTEGER NOT NULL", "users(id) ON DELETE CASCADE"),
            ("token_hash", "TEXT NOT NULL", None),
            ("token_type", "TEXT NOT NULL", None),
            ("expires_at", "TIMESTAMPTZ NOT NULL", None),
            ("used_at", "TIMESTAMPTZ", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "seller_wechat_accounts": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("user_id", "INTEGER NOT NULL", "users(id) ON DELETE CASCADE"),
            ("openid", "TEXT NOT NULL", None),
            ("unionid", "TEXT", None),
            ("bound_at", "TIMESTAMPTZ DEFAULT NOW()", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
        ],
        "user_phones": [
            ("id", "BIGSERIAL PRIMARY KEY", None),
            ("user_id", "INTEGER NOT NULL", "users(id) ON DELETE CASCADE"),
            ("phone", "TEXT NOT NULL", None),
            ("is_primary", "BOOLEAN NOT NULL DEFAULT FALSE", None),
            ("verified", "BOOLEAN NOT NULL DEFAULT FALSE", None),
            ("created_at", "TIMESTAMPTZ DEFAULT NOW()", None),
            ("verified_at", "TIMESTAMPTZ", None),
            ("deleted_at", "TIMESTAMPTZ", None),
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
    from app.models.saved_product import SavedProduct
    from app.models.review import Review
    from app.models.auth_token import AuthToken
    from app.models.seller_wechat_account import SellerWechatAccount
    from app.models.user_phone import UserPhone

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Detect whether email_verified_at already exists before _sync_columns,
        # so we can backfill pre-existing accounts exactly once.
        ev_result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'email_verified_at')"
        ))
        email_verified_existed = ev_result.scalar()

        await conn.run_sync(Base.metadata.create_all)
        await _sync_columns(conn)
        await _migrate_embedding_dimension(conn)
        # Drop unique constraint on sku if it exists (allows duplicate SKUs across sellers)
        try:
            await conn.execute(text(
                "ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key"
            ))
        except Exception as e:
            logger.warning("Drop products_sku_key failed: %s", e)

        # Users: allow the same email across roles (buyer + seller)
        try:
            await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key"))
        except Exception as e:
            logger.warning("Drop users_email_key failed: %s", e)
        try:
            await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_email"))
        except Exception as e:
            logger.warning("Drop uq_users_email failed: %s", e)
        try:
            await conn.execute(text("DROP INDEX IF EXISTS ix_users_email"))
        except Exception as e:
            logger.warning("Drop ix_users_email failed: %s", e)
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_role ON users (email, role)"
            ))
        except Exception as e:
            logger.warning("Create uq_users_email_role failed: %s", e)
        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
        except Exception as e:
            logger.warning("Create ix_users_email failed: %s", e)

        # seller_inquiries.inquiry_id: make nullable (send-inquiry flow does not link an Inquiry record)
        try:
            await conn.execute(text(
                "ALTER TABLE seller_inquiries ALTER COLUMN inquiry_id DROP NOT NULL"
            ))
        except Exception as e:
            logger.warning("Drop NOT NULL on seller_inquiries.inquiry_id failed: %s", e)

        # users.email / users.password_hash: make nullable so WeChat-created sellers
        # can exist without an email or password.
        try:
            await conn.execute(text(
                "ALTER TABLE users ALTER COLUMN email DROP NOT NULL"
            ))
        except Exception as e:
            logger.warning("Drop NOT NULL on users.email failed: %s", e)
        try:
            await conn.execute(text(
                "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"
            ))
        except Exception as e:
            logger.warning("Drop NOT NULL on users.password_hash failed: %s", e)

        # reviews: drop product_id (reviews now target sellers instead of products)
        try:
            await conn.execute(text("ALTER TABLE reviews DROP COLUMN IF EXISTS product_id"))
        except Exception as e:
            logger.warning("Drop reviews.product_id failed: %s", e)

        # Email verification: mark accounts that existed before the feature as
        # verified (runs only on the first deploy that introduces the column).
        if not email_verified_existed:
            try:
                await conn.execute(text(
                    "UPDATE users SET email_verified_at = COALESCE(created_at, NOW()) "
                    "WHERE email_verified_at IS NULL"
                ))
            except Exception as e:
                logger.warning("email_verified_at backfill failed: %s", e)

        # Phone numbers: backfill legacy users.phone as primary phone records.
        # Idempotent — only inserts a row when none exists for that user/phone.
        try:
            await conn.execute(text(
                "INSERT INTO user_phones (user_id, phone, is_primary, verified, created_at) "
                "SELECT u.id, u.phone, true, true, COALESCE(u.created_at, NOW()) "
                "FROM users u "
                "WHERE u.phone IS NOT NULL "
                "  AND NOT EXISTS ("
                "    SELECT 1 FROM user_phones up "
                "    WHERE up.user_id = u.id AND up.phone = u.phone AND up.deleted_at IS NULL"
                "  )"
            ))
        except Exception as e:
            logger.warning("user_phones backfill failed: %s", e)

        # Phone uniqueness: at most one active primary per user, and globally
        # unique active phone numbers.
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_phones_active_phone "
                "ON user_phones (phone) WHERE deleted_at IS NULL"
            ))
        except Exception as e:
            logger.warning("user_phones active-phone unique index failed: %s", e)
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_phones_primary "
                "ON user_phones (user_id) WHERE is_primary = true AND deleted_at IS NULL"
            ))
        except Exception as e:
            logger.warning("user_phones primary unique index failed: %s", e)

        # ── Product indexes: ensure these exist even on pre-existing tables ──
        # (model index=True only applies on fresh create_all, not migrated DBs).
        for stmt, label in [
            ("CREATE INDEX IF NOT EXISTS ix_products_is_active ON products (is_active)", "is_active"),
            ("CREATE INDEX IF NOT EXISTS ix_products_seller_active ON products (seller_id, is_active)", "seller_active"),
            ("CREATE INDEX IF NOT EXISTS ix_products_active_created ON products (is_active, created_at DESC)", "active_created"),
            ("CREATE INDEX IF NOT EXISTS ix_products_category ON products (category)", "category"),
            ("CREATE INDEX IF NOT EXISTS ix_products_active_embed_status ON products (is_active, embedding_status)", "active_embed_status"),
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                logger.warning("Create product index %s failed: %s", label, e)

        # ── saved_products: DB-level unique(user_id, product_id) ──
        # The ORM UniqueConstraint only applies on fresh tables; this ensures it
        # on migrated DBs too, closing a race that allows duplicate favorites.
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_products_user_product "
                "ON saved_products (user_id, product_id)"
            ))
        except Exception as e:
            logger.warning("Create uq_saved_products_user_product failed: %s", e)

        # ── reviews: DB-level unique(seller_id, user_id) ──
        # Backs the application-level upsert so concurrent reviews can't duplicate.
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_seller_user "
                "ON reviews (seller_id, user_id)"
            ))
        except Exception as e:
            logger.warning("Create uq_reviews_seller_user failed: %s", e)


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
