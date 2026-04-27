"""
Run inside the API container:
  docker exec -it eaih_api python scripts/run_ingest.py
  docker exec -it eaih_api python scripts/run_ingest.py --mode small
"""
import sys
import os
import time

# Allow running from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.ingestion import ingest_chunks

mode = "small" if "--mode" in sys.argv and sys.argv[sys.argv.index("--mode") + 1] == "small" else "medium"

print(f"[ingest] Starting {mode} ingestion …")
t0 = time.time()
stats = ingest_chunks(mode)
elapsed = time.time() - t0
print(f"[ingest] Done in {elapsed:.1f}s — {stats['files']} files, {stats['chunks']} chunks indexed")
