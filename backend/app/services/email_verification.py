"""Issue short-lived, single-use email confirmation codes."""
from datetime import datetime, timedelta, timezone

from app.core.security import generate_email_code, hash_email_code
from app.models.auth_token import AuthToken

CODE_LIFETIME = timedelta(minutes=5)
MAX_CODE_ATTEMPTS = 5


async def issue_email_code(db, user_id: int) -> str:
    code = generate_email_code()
    db.add(AuthToken(
        user_id=user_id,
        token_hash=hash_email_code(user_id, code),
        token_type="email_verification",
        expires_at=datetime.now(timezone.utc) + CODE_LIFETIME,
    ))
    return code
