import os
import psycopg
from dotenv import load_dotenv, find_dotenv

# 強制從根目錄搜尋並載入 .env，確保 override 舊的環境變數
env_path = find_dotenv()
if env_path:
    print(f"🔍 成功找到並載入環境變數檔案: {env_path}")
    load_dotenv(env_path, override=True)
else:
    print("⚠️ 警告：找不到 .env 檔案，請確認檔案存在於專案根目錄！")

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:810126@localhost:5432/eaih_app")

def get_conn():
    # 優先檢查是否有完整的 DATABASE_URL，這能簡化連線邏輯並減少設定錯誤
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            return psycopg.connect(db_url, connect_timeout=5)
        except Exception as e:
            print(f"❌ 使用 DATABASE_URL 連線失敗: {e}")
            # 若 DATABASE_URL 失敗，則繼續嘗試使用下方的個別變數 fallback

    # 使用 strip() 確保不會因為 .env 尾端的空白字元導致認證失敗
    host = (os.getenv("POSTGRES_HOST") or "localhost").strip()
    port = (os.getenv("POSTGRES_PORT") or "5432").strip()
    dbname = (os.getenv("POSTGRES_DB") or "eaih_app").strip()
    user = (os.getenv("POSTGRES_USER") or "postgres").strip()
    password = (os.getenv("POSTGRES_PASSWORD") or "810126").strip()
    
    print(f"🔌 嘗試連線：Host={host}, DB={dbname}, User={user} (密碼長度: {len(password) if password else 0})")
    
    try:
        return psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
    except Exception as e:
        print(f"❌ 無法連線至資料庫: {e}")
        print(f"💡 請檢查 PostgreSQL 服務是否啟動，或 User/Password 是否正確。")
        raise e
