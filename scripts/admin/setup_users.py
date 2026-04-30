import os
import sys
import psycopg
from dotenv import load_dotenv

# 確保能引用到 backend 模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.auth import hash_password

load_dotenv()

def main():
    print("🚀 正在建立預設使用者帳號...")
    
    # 定義要建立的帳號資料 (帳號, 密碼, 角色)
    users_to_create = [
        ("aa", "123", "admin"),   # 管理者
        ("sas", "11", "user")     # 一般使用者
    ]

    try:
        with psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "eaih_app"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD"),
        ) as conn:
            with conn.cursor() as cur:
                for username, password, role in users_to_create:
                    p_hash = hash_password(password)
                    cur.execute("""
                        INSERT INTO users (username, password_hash, role, is_active)
                        VALUES (%s, %s, %s, true)
                        ON CONFLICT (username) DO UPDATE 
                        SET password_hash = EXCLUDED.password_hash, role = EXCLUDED.role, is_active = true;
                    """, (username, p_hash, role))
            conn.commit()
        print("✅ 預設帳號已建立/更新完成：\n   - 管理者: aa / 123\n   - 使用者: sas / 11")
    except Exception as e:
        print(f"❌ 建立失敗: {e}")

if __name__ == "__main__":
    main()