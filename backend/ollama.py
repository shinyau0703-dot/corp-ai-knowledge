import json
import urllib.request
from backend.config import OLLAMA_HOST

def generate(prompt: str, model: str = "llama3:latest") -> str:
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

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return result["response"].strip()
