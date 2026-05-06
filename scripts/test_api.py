import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_search():
    print("--- 1. 嘗試登入 ---")
    login_url = f"{BASE_URL}/api/login"
    try:
        login_resp = requests.post(login_url, json={"username": "admin"})
        login_resp.raise_for_status()
        token = login_resp.json().get("access_token")
        print(f"✅ 登入成功，取得 Token: {token[:20]}...")
    except requests.exceptions.ConnectionError:
        print(f"❌ 無法連線至伺服器 ({BASE_URL})。請確認是否已執行: uvicorn backend.main:app --reload")
        return
    except Exception as e:
        print(f"❌ 登入失敗: {e}")
        return

    print("\n--- 2. 測試搜尋 API ---")
    search_url = f"{BASE_URL}/api/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": "如何設定授權伺服器",
        "mode": "medium",
        "top_k": 3
    }
    
    try:
        # 使用 json= 參數會自動設定 Content-Type 並處理編碼
        response = requests.post(search_url, json=payload, headers=headers)
        if response.status_code == 200:
            print("✅ 搜尋成功！回傳結果：")
            results = response.json()
            items = results.get("items", [])
            if not items:
                print("⚠️  API 回傳成功，但沒有找到符合的文檔內容。")
            for i, item in enumerate(items, 1):
                print(f"[{i}] 來源: {item['source_file']} (產品: {item['product']})")
                print(f"    內容摘要: {item['text'][:100]}...")
        else:
            print(f"❌ 搜尋失敗，狀態碼: {response.status_code}")
            print(f"    錯誤訊息: {response.text}")
    except Exception as e:
        print(f"❌ 發送請求時發生錯誤: {e}")

if __name__ == "__main__":
    # 檢查伺服器是否在執行
    print(f"正在檢查 API 伺服器: {BASE_URL}")
    test_search()