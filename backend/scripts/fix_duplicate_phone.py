"""Fix duplicate phone 18565511523 on Railway PostgreSQL.

State: user_phones table does NOT exist yet (old deploy). The duplicate phone
lives in users.phone (users id=9 and id=10 both have 18565511523). When the new
code deploys, init_db() creates user_phones, backfills from users.phone, then
tries CREATE UNIQUE INDEX — which would FAIL on the duplicate.

This script:
 1. Nulls user id=10's phone (keeps id=9's — the seller with a name).
 2. Creates the user_phones table (same DDL as _sync_columns).
 3. Backfills from users.phone (no duplicates now).
 4. Creates both unique indexes.
 5. Verifies.
Does NOT delete any users. Does NOT touch other phones.
"""
import os, sys, re
from pathlib import Path

def get_dsn():
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        env = Path(__file__).parent.parent / ".env"
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and not line.startswith("DATABASE_URL_SYNC"):
                dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not dsn: sys.exit(1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
    if "?" not in dsn: dsn += "?sslmode=require"
    elif "sslmode" not in dsn: dsn += "&sslmode=require"
    return dsn

def main():
    import psycopg2
    conn = psycopg2.connect(get_dsn())
    conn.autocommit = True  # each statement independent — DDL-safe, no aborted-tx carryover
    cur = conn.cursor()
    PHONE = "18565511523"

    # ── 1. Show current state ──
    print(f"=== Before: users with phone = '{PHONE}' ===")
    cur.execute("SELECT id, email, role, name, phone FROM users WHERE phone = %s ORDER BY id", (PHONE,))
    rows = cur.fetchall()
    for r in rows:
        print(f"  id={r[0]}  email={r[1]}  role={r[2]}  name={r[3]}  phone={r[4]}")

    # ── 2. Fix: keep id=9 (seller, has name), null id=10 (buyer, no name) ──
    # "18565511523 可以直接删除" + "保留一条记录" → keep one user's phone, null the other.
    # Don't delete the user — only null the phone column on the duplicate.
    if len(rows) >= 2:
        keep_id = rows[0][0]  # lowest id = id=9 (seller, has name "test company")
        for r in rows[1:]:
            dup_id = r[0]
            cur.execute("UPDATE users SET phone = NULL WHERE id = %s", (dup_id,))
            print(f"\n  Nulled phone for user id={dup_id} (email={r[1]}, role={r[2]}) — kept id={keep_id}")
    else:
        print("  No duplicates to fix in users.phone")

    # ── 3. Verify users.phone no longer has the duplicate ──
    print(f"\n=== After: users with phone = '{PHONE}' ===")
    cur.execute("SELECT id, email, role, phone FROM users WHERE phone = %s", (PHONE,))
    for r in cur.fetchall():
        print(f"  id={r[0]}  email={r[1]}  role={r[2]}  phone={r[3]}")
    cur.execute("SELECT count(*) FROM users WHERE phone = %s", (PHONE,))
    print(f"  Count: {cur.fetchone()[0]}")

    # ── 4. Create user_phones table (if not exists) ──
    print(f"\n=== Create user_phones table (if not exists) ===")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_phones (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            phone TEXT NOT NULL,
            is_primary BOOLEAN NOT NULL DEFAULT FALSE,
            verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            verified_at TIMESTAMPTZ,
            deleted_at TIMESTAMPTZ
        )
    """)
    print("  user_phones table ready")

    # ── 5. Backfill from users.phone (idempotent) ──
    print(f"\n=== Backfill user_phones from users.phone ===")
    cur.execute("""
        INSERT INTO user_phones (user_id, phone, is_primary, verified, created_at)
        SELECT u.id, u.phone, true, true, COALESCE(u.created_at, NOW())
        FROM users u
        WHERE u.phone IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM user_phones up
            WHERE up.user_id = u.id AND up.phone = u.phone AND up.deleted_at IS NULL
          )
    """)
    print(f"  Backfilled {cur.rowcount} row(s)")

    # ── 6. Check for any remaining duplicate active phones ──
    print(f"\n=== Check duplicate active phones in user_phones ===")
    cur.execute("""
        SELECT phone, count(*) FROM user_phones
        WHERE deleted_at IS NULL
        GROUP BY phone HAVING count(*) > 1
    """)
    dups = cur.fetchall()
    print(f"  Duplicate groups: {len(dups)}")
    for phone, cnt in dups:
        print(f"    {phone}: {cnt}")

    # ── 7. Create unique indexes ──
    print(f"\n=== Create unique indexes ===")
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_phones_active_phone "
            "ON user_phones (phone) WHERE deleted_at IS NULL"
        )
        print("  uq_user_phones_active_phone: OK")
    except Exception as e:
        print(f"  uq_user_phones_active_phone: FAILED — {e}")

    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_phones_primary "
            "ON user_phones (user_id) WHERE is_primary = true AND deleted_at IS NULL"
        )
        print("  uq_user_phones_primary: OK")
    except Exception as e:
        print(f"  uq_user_phones_primary: FAILED — {e}")

    # ── 8. Final verification ──
    print(f"\n=== Final verification: user_phones indexes ===")
    cur.execute(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE tablename = 'user_phones' ORDER BY indexname"
    )
    indexes = cur.fetchall()
    found_active = False
    found_primary = False
    for name, defn in indexes:
        print(f"  {name}")
        if name == "uq_user_phones_active_phone": found_active = True
        if name == "uq_user_phones_primary": found_primary = True
    print(f"\n  uq_user_phones_active_phone exists: {found_active}")
    print(f"  uq_user_phones_primary exists:      {found_primary}")

    print(f"\n=== user_phones WHERE phone = '{PHONE}' AND deleted_at IS NULL ===")
    cur.execute("SELECT id, user_id, phone, is_primary, verified FROM user_phones WHERE phone = %s AND deleted_at IS NULL", (PHONE,))
    for r in cur.fetchall():
        print(f"  id={r[0]}  user_id={r[1]}  phone={r[2]}  is_primary={r[3]}  verified={r[4]}")

    cur.close(); conn.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
