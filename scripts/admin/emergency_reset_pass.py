import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

def reset():
    # 直接從 .env 讀取你想要的密碼
    db_pass = os.getenv("POSTGRES_PASSWORD")
    if not db_pass:
        print("❌ 錯誤：請先在 .env 檔案中設定 POSTGRES_PASSWORD")
        return
    
    try:
        print("正在嘗試連線到本地 PostgreSQL (Trust 模式)...")
        # 使用 127.0.0.1 並明確提供空密碼欄位，強制繞過驅動程式預檢
        conninfo = "host=127.0.0.1 port=5432 dbname=postgres user=postgres password='' connect_timeout=5"

        try:
            conn = psycopg.connect(conninfo, autocommit=True)
        except Exception as e:
            print(f"嘗試 127.0.0.1 失敗: {e}，改試 localhost...")
            conn = psycopg.connect("host=localhost port=5432 dbname=postgres user=postgres password='' connect_timeout=5", autocommit=True)

        cur = conn.cursor()
        
        print(f"✅ 連線成功！正在將 postgres 密碼同步為 .env 中的設定...")
        cur.execute("ALTER USER postgres WITH PASSWORD %s;", (db_pass,))
        
        print("\n✅ postgres 密碼已成功更新！")
        print("-" * 40)
        print("接下來請執行以下步驟還原安全性：")
        print("1. 開啟 pg_hba.conf，將所有的 'trust' 改回 'scram-sha-256'")
        print("2. 儲存檔案並『重新啟動』PostgreSQL 服務")
        print("3. 執行指令: python scripts/init_db_simple.py")
        print("-" * 40)

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ 重設失敗: {e}")
        print("\n💡 [解決方案] 如果依然失敗，請確保 pg_hba.conf 中這兩行都改成了 trust：")
        print("host    all             all             127.0.0.1/32            trust")
        print("host    all             all             ::1/128                 trust")
        print("修改後請務必『重新啟動』PostgreSQL 服務。")

if __name__ == "__main__":
    reset()