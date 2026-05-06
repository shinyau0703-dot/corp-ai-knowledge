import json
import urllib.request
import urllib.error
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

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Ollama model '{model}' not found. Please run 'ollama pull {model}' on the Ollama host.")
        raise RuntimeError(f"Ollama API error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to Ollama at {OLLAMA_HOST}: {e.reason}")

    return result["response"].strip()
