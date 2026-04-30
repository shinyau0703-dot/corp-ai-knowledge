import sys
import os
import psycopg
from dotenv import load_dotenv

# 確保能引用到 backend 模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import hash_password
load_dotenv()

def main():
    if len(sys.argv) >= 3:
        # 支援指令模式: python scripts/create_user.py testuser password123 user
        username = sys.argv[1]
        password = sys.argv[2]
        role = sys.argv[3] if len(sys.argv) > 3 else "user"
    else:
        # 支援互動模式
        username = input("使用者名稱: ").strip()
        password = input("密碼: ").strip()
        role = input("角色 (user/editor/admin) [預設 user]: ").strip() or "user"

    if role not in ('user', 'editor', 'admin'):
        print(f"❌ 錯誤：不支援的角色類型 '{role}'。僅限 user, editor, admin。")
        return

    password_hash = hash_password(password)

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "eaih_app"),
            user="postgres",
            password=os.getenv("POSTGRES_PASSWORD"),
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users(username, password_hash, role, is_active)
                    VALUES(%s, %s, %s, true)
                    ON CONFLICT(username) DO UPDATE
                    SET password_hash=EXCLUDED.password_hash, role=EXCLUDED.role, is_active=true
                """, (username, password_hash, role))
            conn.commit()
        print(f"✅ 成功：使用者 '{username}' (角色: {role}) 已建立或更新。")
    except Exception as e:
        print(f"❌ 建立失敗：{e}")

if __name__ == "__main__":
    main()