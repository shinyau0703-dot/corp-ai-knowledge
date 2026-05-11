import json
import urllib.request
import urllib.error
from backend.config import OLLAMA_HOST, DEFAULT_LLM_MODEL

def generate(prompt: str, model: str = DEFAULT_LLM_MODEL) -> str:
    url = f"{OLLAMA_HOST}/api/generate"
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"找不到 Ollama 模型 '{model}'。請在主機執行 'ollama pull {model}'。")
        raise RuntimeError(f"Ollama API 錯誤: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"無法連線至 Ollama 服務 ({OLLAMA_HOST}): {e.reason}")

    return result["response"].strip()
