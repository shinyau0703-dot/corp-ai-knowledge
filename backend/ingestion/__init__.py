import json
import re
from pathlib import Path
import chromadb
from backend.config import CHUNKS_MEDIUM_DIR, CHUNKS_SMALL_DIR, VECTOR_MEDIUM_DIR, VECTOR_SMALL_DIR
from backend.embedder import embed_texts

# Map filename prefixes to clean product names
_PRODUCT_MAP = {
    "AltairHyperMeshCFD": "HyperMesh CFD",
    "AltairHyperMesh":    "HyperMesh",
    "AltairHyperWorks":   "HyperWorks",
    "AltairConnectMe":    "ConnectMe",
    "AltairFluxAndFluxMotor": "Flux / FluxMotor",
    "AltairPhysicsAI":    "PhysicsAI",
    "AltairSimLab":       "SimLab",
    "Altair_Feko":        "Feko",
    "TwinActivate":       "Twin Activate",
    "Twin_Activate":      "Twin Activate",
    "Cast_":              "Cast",
    "Compose_":           "Compose",
    "Inspire_":           "Inspire",
    "Form_":              "Form",
    "Extrude_":           "Extrude",
    "Mold_":              "Mold",
    "PolyFoam_":          "PolyFoam",
    "Studio_":            "Studio",
}

_VERSION_RE = re.compile(r'(?:_|v)(\d{4}(?:[._]\d+)*)(?:_|$)')


def _clean_product(raw: str) -> str:
    for prefix, name in _PRODUCT_MAP.items():
        if raw.startswith(prefix):
            return name
    return re.sub(r'^Altair_?', '', raw).strip("_- ")


def _parse_sw_part(part: str) -> dict:
    """Parse SW flat filename like AltairHyperWorks_2024_1_InstallGuide_pdf."""
    part = re.sub(r'_?pdf$', '', part, flags=re.IGNORECASE)

    m = _VERSION_RE.search(part)
    if m:
        raw_ver = m.group(1).replace("_", ".")
        product_raw = part[: m.start()].strip("_")
        doc_raw = part[m.end():].strip("_").replace("_", " ")
    else:
        # Fallback: last token after product name
        product_raw = part
        raw_ver = ""
        doc_raw = ""

    return {
        "product": _clean_product(product_raw),
        "version": raw_ver,
        "doc_type": doc_raw,
    }


def parse_filename_metadata(stem: str) -> dict:
    """Derive product / version / doc_type from chunk JSON filename stem.

    PBS filenames:  …__PBS__PBS__2026__PBSAdmin2026.0_pdf
    SW  filenames:  …__SW__AltairHyperWorks_2024_InstallGuide_pdf
    """
    parts = stem.split("__")

    if len(parts) < 3:
        return {"product": stem, "version": "", "doc_type": ""}

    group = parts[2]

    if group == "PBS":
        # parts: [cat, subcat, PBS, PBS, version, docname_pdf]
        version = parts[4] if len(parts) > 4 else ""
        doc_raw = parts[5] if len(parts) > 5 else ""
        doc_raw = re.sub(r'_?pdf$', '', doc_raw, flags=re.IGNORECASE)
        doc_type = re.sub(r'\d{4}(?:[._]\d+)*', '', doc_raw).strip("_. ")
        return {"product": "PBS", "version": version, "doc_type": doc_type}

    if group == "SW" and len(parts) >= 4:
        return _parse_sw_part(parts[3])

    # Unknown group
    return _parse_sw_part(parts[-1])


def list_products(mode: str = "medium") -> list[dict]:
    """Return [{product, versions: [...]}] sorted alphabetically, from chunk files."""
    chunks_dir = CHUNKS_MEDIUM_DIR if mode == "medium" else CHUNKS_SMALL_DIR
    catalog: dict[str, set] = {}
    for jf in chunks_dir.glob("*.json"):
        m = parse_filename_metadata(jf.stem)
        p = m["product"]
        if p:
            catalog.setdefault(p, set())
            if m["version"]:
                catalog[p].add(m["version"])
    return [
        {"product": p, "versions": sorted(catalog[p], reverse=True)}
        for p in sorted(catalog)
    ]


def ingest_chunks(mode: str = "medium") -> dict:
    """Embed chunk JSONs and write to ChromaDB. Returns stats dict."""
    if mode == "medium":
        chunks_dir, vector_dir, col_name = CHUNKS_MEDIUM_DIR, VECTOR_MEDIUM_DIR, "medium_chunks"
    else:
        chunks_dir, vector_dir, col_name = CHUNKS_SMALL_DIR, VECTOR_SMALL_DIR, "small_chunks"

    client = chromadb.PersistentClient(path=str(vector_dir))
    try:
        client.delete_collection(col_name)
    except Exception:
        pass
    collection = client.create_collection(col_name)

    chunk_files = sorted(chunks_dir.glob("*.json"))
    all_ids, all_texts, all_metas = [], [], []

    for jf in chunk_files:
        file_meta = parse_filename_metadata(jf.stem)
        try:
            with open(jf, encoding="utf-8") as f:
                chunks = json.load(f)
        except Exception:
            continue
        for chunk in chunks:
            cid = f"{jf.stem}__{chunk['chunk_index']}"
            all_ids.append(cid)
            all_texts.append(chunk["text"])
            all_metas.append({
                "source_file": jf.name,
                "source_path": jf.name,
                "file_type": str(chunk.get("file_type", "pdf")),
                "chunk_index": int(chunk["chunk_index"]),
                "char_count": int(chunk.get("char_count", len(chunk["text"]))),
                "product": file_meta["product"],
                "version": file_meta["version"],
                "doc_type": file_meta["doc_type"],
            })

    BATCH = 64
    for i in range(0, len(all_ids), BATCH):
        embeddings = embed_texts(all_texts[i: i + BATCH])
        collection.add(
            ids=all_ids[i: i + BATCH],
            embeddings=embeddings,
            documents=all_texts[i: i + BATCH],
            metadatas=all_metas[i: i + BATCH],
        )

    return {"mode": mode, "files": len(chunk_files), "chunks": len(all_ids)}
