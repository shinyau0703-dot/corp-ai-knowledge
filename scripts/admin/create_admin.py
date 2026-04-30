import sys
import os
import psycopg
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import hash_password
load_dotenv()

if len(sys.argv) == 3:
    # 支援指令模式: python scripts/create_admin.py admin 1234
    username = sys.argv[1]
    password = sys.argv[2]
else:
    # 支援互動模式
    username = input("admin username: ").strip()
    password = input("admin password: ").strip()

password_hash = hash_password(password)

try:
    # 改用 postgres 超級使用者帳號進行連線，確保具備寫入 users 資料表的權限
    with psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "eaih_app"),
        user="postgres",
        password=os.getenv("POSTGRES_PASSWORD", "810126"),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users(username, password_hash, role, is_active)
                VALUES(%s, %s, 'admin', true)
                ON CONFLICT(username) DO UPDATE
                SET password_hash=EXCLUDED.password_hash, role='admin', is_active=true
            """, (username, password_hash))
        conn.commit()
    print(f"\n✅ 成功：帳號 '{username}' 密碼已設為 '{password}'。")
    print(f"現在您可以前往 http://localhost:3000 登入。")
except Exception as e:
    print(f"\n❌ 連線失敗：無法存取資料庫。")
    print(f"錯誤訊息: {e}")
    print("-" * 30)
    print("請檢查以下項目：")
    print("1. PostgreSQL 服務是否已啟動？ (請在 Windows 搜尋 '服務' 並檢查 PostgreSQL)")
    print(f"2. 是否已手動建立資料庫 '{os.getenv('POSTGRES_DB', 'eaih_app')}'？")
    print("3. .env 檔案中的 POSTGRES_PASSWORD 是否正確？")
