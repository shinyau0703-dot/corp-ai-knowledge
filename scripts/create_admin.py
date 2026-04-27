import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from backend.database import get_conn

username = input("admin username: ").strip()
password = input("admin password: ").strip()
password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users(username, password_hash, role, is_active)
            VALUES(%s, %s, 'admin', true)
            ON CONFLICT(username) DO UPDATE
            SET password_hash=EXCLUDED.password_hash, role='admin', is_active=true
        """, (username, password_hash))
    conn.commit()

print("admin ready")
