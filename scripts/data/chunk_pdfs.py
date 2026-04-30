"""
Extract text from PDFs in data/raw/ and write chunk JSONs to data/chunks/

Usage:
  python scripts/data/chunk_pdfs.py              # medium (default)
  python scripts/data/chunk_pdfs.py --mode small
"""
import sys
import os
import re
import json
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    import fitz  # pymupdf
except ImportError:
    print("[error] pymupdf not installed. Run: pip install pymupdf")
    sys.exit(1)

from backend.config import RAW_DIR, CHUNKS_MEDIUM_DIR, CHUNKS_SMALL_DIR

# ---------------------------------------------------------------------------
# Product directory → display name
# ---------------------------------------------------------------------------
PRODUCT_DIR_MAP = {
    "activate-libs":  "Activate Libraries",
    "connectme":      "ConnectMe",
    "electronics":    "Electronics",
    "feko":           "Feko",
    "flux":           "Flux / FluxMotor",
    "hypermesh-cfd":  "HyperMesh CFD",
    "hyperworks":     "HyperWorks",
    "cast":           "Cast",
    "compose":        "Compose",
    "extrude":        "Extrude",
    "form":           "Form",
    "inspire":        "Inspire",
    "mold":           "Mold",
    "polyfoam":       "PolyFoam",
    "license":        "License Management",
    "pbs":            "PBS Professional",
    "physicsai":      "PhysicsAI",
    "simlab":         "SimLab",
    "studio":         "Studio",
    "twin-activate":  "Twin Activate",
    "floefd":         "FLOEFD",
    "flotherm":       "Flotherm",
    "star-ccm+":      "STAR-CCM+",
}

VENDOR_DIRS    = {"altair", "siemens-cfd"}
PLATFORM_DIRS  = {"catia v5", "creo", "nx", "sc", "solid edge", "standalone"}
VERSION_RE     = re.compile(r'(?<![a-zA-Z])(\d{4}(?:[._]\d+)*|v\d+(?:[._]\d+)*)(?![a-zA-Z0-9])', re.IGNORECASE)

CHUNK_SIZE    = {"medium": 800,  "small": 400}
CHUNK_OVERLAP = {"medium": 150,  "small": 80}


def _looks_like_version(name: str) -> bool:
    return bool(re.fullmatch(r'\d{4}(?:[._]\d+)*|\d+', name))


def _version_from_filename(stem: str) -> str:
    m = VERSION_RE.search(stem)
    return m.group(1).replace("_", ".") if m else ""


def _get_product_version(pdf_path: Path) -> tuple[str, str]:
    """Derive (product, version) from path relative to data/raw/."""
    dir_parts = list(pdf_path.relative_to(RAW_DIR).parts[:-1])  # skip filename

    # Drop vendor prefix
    if dir_parts and dir_parts[0].lower() in VENDOR_DIRS:
        dir_parts = dir_parts[1:]

    product_dir = ""
    version_from_dir = ""
    i = 0
    while i < len(dir_parts):
        part = dir_parts[i]
        low = part.lower()
        if _looks_like_version(part):
            version_from_dir = part.replace("_", ".")
        elif low in PLATFORM_DIRS:
            pass  # skip (CATIA V5, NX, etc.)
        elif not product_dir:
            # Special case: altair/inspire/* — use the child subdir as product
            if low == "inspire" and i + 1 < len(dir_parts) and not _looks_like_version(dir_parts[i + 1]):
                i += 1
                product_dir = dir_parts[i]
            else:
                product_dir = part
        i += 1

    product = PRODUCT_DIR_MAP.get(product_dir.lower(), product_dir.replace("-", " ").title())
    version = version_from_dir or _version_from_filename(pdf_path.stem)
    return product, version


def _extract_text(pdf_path: Path) -> str:
    try:
        doc = fitz.open(str(pdf_path))
        return "\n".join(page.get_text() for page in doc).strip()
    except Exception as e:
        print(f"  [warn] {pdf_path.name}: {e}")
        return ""


def _split_chunks(text: str, size: int, overlap: int) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start: start + size])
        start += size - overlap
    return chunks


def process_pdf(pdf_path: Path, chunks_dir: Path, mode: str) -> int:
    product, version = _get_product_version(pdf_path)
    text = _extract_text(pdf_path)
    if not text:
        return 0

    raw_chunks = _split_chunks(text, CHUNK_SIZE[mode], CHUNK_OVERLAP[mode])
    chunks = [
        {"chunk_index": i, "text": c, "char_count": len(c)}
        for i, c in enumerate(raw_chunks) if c.strip()
    ]
    if not chunks:
        return 0

    # Build output filename from relative path
    rel_parts = pdf_path.relative_to(RAW_DIR).parts
    safe_name = "__".join(p.replace(" ", "_") for p in rel_parts[:-1] + (pdf_path.stem,)) + ".json"

    payload = {
        "product": product,
        "version": version,
        "source_file": pdf_path.name,
        "chunks": chunks,
    }
    with open(chunks_dir / safe_name, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    return len(chunks)


def main():
    mode = "small" if "--mode" in sys.argv and sys.argv[sys.argv.index("--mode") + 1] == "small" else "medium"
    chunks_dir = CHUNKS_MEDIUM_DIR if mode == "medium" else CHUNKS_SMALL_DIR
    chunks_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(RAW_DIR.rglob("*.pdf"))
    print(f"[chunk] mode={mode}  {len(pdfs)} PDFs found in {RAW_DIR}")

    t0 = time.time()
    total_chunks = 0
    failed = 0
    for i, pdf in enumerate(pdfs, 1):
        n = process_pdf(pdf, chunks_dir, mode)
        if n == 0:
            failed += 1
        total_chunks += n
        if i % 100 == 0 or i == len(pdfs):
            print(f"  [{i:4d}/{len(pdfs)}]  {total_chunks} chunks  ({failed} skipped)")

    elapsed = time.time() - t0
    print(f"[chunk] Done in {elapsed:.1f}s — {len(pdfs)} PDFs → {total_chunks} chunks  ({failed} skipped)")


if __name__ == "__main__":
    main()
