import psycopg
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# 確保能引用到 backend 模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.auth import hash_password

load_dotenv()

def init_db():
    DB_NAME = os.getenv("POSTGRES_DB", "eaih_app")
    DB_PASS = os.getenv("POSTGRES_PASSWORD", "810126")
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    # 這裡預設使用 postgres 超級使用者來進行修復
    SUPER_USER = "postgres" 
    
    print(f"🚀 開始初始化資料庫環境 (使用帳號: {SUPER_USER})...")
    
    try:
        # 1. 先連線到系統預設的 postgres 資料庫
        conn = psycopg.connect(
            conninfo=f"host=localhost port=5432 dbname=postgres user={SUPER_USER} password={DB_PASS} connect_timeout=5",
            autocommit=True,
        )
        cur = conn.cursor()
        
        # 2. 建立或更新 eaih_app 使用者及其密碼
        print(f"正在同步使用者 {DB_USER} 的密碼...")
        cur.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = '{DB_USER}') THEN CREATE ROLE {DB_USER} LOGIN PASSWORD '{DB_PASS}'; END IF; END $$;")
        cur.execute(f"ALTER ROLE {DB_USER} WITH PASSWORD '{DB_PASS}';")
        cur.execute(f"ALTER ROLE {DB_USER} CREATEDB;") # 賦予建立資料庫權限

        # 3. 建立資料庫 (若不存在)
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER}")
            print(f"✅ 資料庫 {DB_NAME} 建立成功！")
        else:
            print(f"ℹ️ 資料庫 {DB_NAME} 已存在，準備更新結構。")
        
        cur.close()
        conn.close()

        # 4. 連線到新建立的資料庫執行初始化 SQL
        print("正在初始化資料表結構 (init.sql)...")
        conn = psycopg.connect(
            conninfo=f"host=localhost port=5432 dbname={DB_NAME} user={SUPER_USER} password={DB_PASS}"
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        sql_path = Path(__file__).parent.parent / "db" / "init.sql"
        if sql_path.exists():
            cur.execute(sql_path.read_text(encoding="utf-8"))
            print("✅ 資料表初始化完成。")
        
        # 5. 直接建立 admin 帳號
        print("正在強制設定測試帳號...")
        
        # 建立管理者 aa / 123
        aa_hash = hash_password("123")
        # 建立使用者 sas / 11
        sas_hash = hash_password("11")

        cur.execute("""
            DELETE FROM users WHERE username IN ('aa', 'sas', 'admin');
            INSERT INTO users(username, password_hash, role, is_active) VALUES('aa', %s, 'admin', true);
            INSERT INTO users(username, password_hash, role, is_active) VALUES('sas', %s, 'user', true);
        """, (aa_hash, sas_hash))
        
        print("\n" + "="*40)
        print("✨ 網站環境已就緒！")
        print("網址：http://localhost:3000")
        print("1. 管理者：aa / 123")
        print("2. 使用者：sas / 11")
        print("="*40)
        
        cur.close()
        conn.close()
    except Exception as e:
        if "password authentication failed" in str(e):
            print(f"\n❌ 密碼錯誤：無法以 '{SUPER_USER}' 身份登入。")
            print(f"請確認 .env 中的 POSTGRES_PASSWORD 是否正確。")
            print("-" * 30)
            print("如果你完全忘記密碼，請依照手冊修改 pg_hba.conf 為 'trust' 模式後，先執行 scripts/emergency_reset_pass.py")
        else:
            print(f"\n❌ 關鍵錯誤: {e}")
        print("\n提示：如果您完全忘記了 PostgreSQL 的密碼，請搜尋 'PostgreSQL 重設 postgres 密碼' 以取得教學。")

if __name__ == "__main__":
    init_db()