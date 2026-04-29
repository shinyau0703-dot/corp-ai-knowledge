import os
import sys
import psycopg
from dotenv import load_dotenv

# 確保能引用到 backend 模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.auth import hash_password

load_dotenv()

def fix_accounts():
    try:
        # 連接到資料庫，優先從 .env 讀取設定
        conn = psycopg.connect(
            dbname=os.getenv("POSTGRES_DB", "eaih_app"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "810126"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        cur = conn.cursor()

        # 1. 先清除可能存在的舊帳號
        print("正在清除舊帳號 (aa, sas)...")
        cur.execute("DELETE FROM users WHERE username IN ('aa', 'sas');")

        # 2. 準備加密後的密碼 (調用專案內建的 bcrypt 邏輯)
        hashed_123 = hash_password("123")
        hashed_11 = hash_password("11")

        # 3. 插入管理者 aa (密碼: 123)
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            ('aa', hashed_123, 'admin')
        )

        # 4. 插入一般使用者 sas (密碼: 11)
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            ('sas', hashed_11, 'user')
        )

        conn.commit()
        print("✅ 帳號建立成功！")
        print("管理者: aa / 123")
        print("使用者: sas / 11")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    fix_accounts()