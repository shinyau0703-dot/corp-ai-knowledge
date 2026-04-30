"""
Reorganize data/raw/ to a uniform vendor/product/version/file.pdf structure.

Changes made:
  1. Flat Altair products (hyperworks, connectme, etc.): extract version from
     filename, create version subdir, move PDF there.
  2. Flat Inspire sub-products (cast, compose, ...): same as above.
  3. FLOEFD: flip platform/version/ → version/platform/ using a temp dir.
  4. Already-versioned products (pbs, flotherm, star-ccm+): skip.

Run with --dry-run to preview, then without to execute.
"""
import sys
import os
import re
import shutil
import io
from pathlib import Path

# Force UTF-8 output so Chinese filenames don't crash on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.config import RAW_DIR

DRY_RUN = "--dry-run" in sys.argv

# Products already in correct vendor/product/version/ structure — skip
SKIP_PRODUCTS = {"pbs"}       # altair/pbs already versioned
SKIP_SIEMENS  = {"flotherm", "star-ccm+"}  # already versioned

# Regex patterns for version extraction (tried in order)
_YEAR_RE    = re.compile(r'(\d{4}(?:[._]\d+)*)')
_VPFX_RE    = re.compile(r'(?i)[_\-\s]v(\d+(?:[._]\d+)*)')
_DECML_RE   = re.compile(r'(\d+\.\d+)')


def extract_version(stem: str) -> str:
    """Extract version string from a PDF stem, normalize _ → ."""
    m = _YEAR_RE.search(stem)
    if m:
        return m.group(1).replace("_", ".")
    m = _VPFX_RE.search(stem)
    if m:
        return m.group(1).replace("_", ".")
    m = _DECML_RE.search(stem)
    if m:
        return m.group(1)
    return "unknown"


def move_file(src: Path, dst: Path):
    if DRY_RUN:
        print(f"  [dry] {src.relative_to(RAW_DIR)}  ->  {dst.relative_to(RAW_DIR)}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    print(f"  {src.relative_to(RAW_DIR)}  ->  {dst.relative_to(RAW_DIR)}")


# ---------------------------------------------------------------------------
# 1. Flat Altair products (direct PDFs in product dir → need version subdir)
# ---------------------------------------------------------------------------
def reorganize_flat(product_dir: Path):
    pdfs = [p for p in product_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    if not pdfs:
        return
    print(f"\n[flat] {product_dir.relative_to(RAW_DIR)}  ({len(pdfs)} PDFs)")
    for pdf in sorted(pdfs):
        version = extract_version(pdf.stem)
        dst = product_dir / version / pdf.name
        move_file(pdf, dst)


# ---------------------------------------------------------------------------
# 2. Flat Inspire sub-products
# ---------------------------------------------------------------------------
def reorganize_inspire(inspire_dir: Path):
    for sub in sorted(inspire_dir.iterdir()):
        if sub.is_dir():
            reorganize_flat(sub)


# ---------------------------------------------------------------------------
# 3. FLOEFD: PLATFORM/VERSION/file.pdf → VERSION/PLATFORM/file.pdf
# ---------------------------------------------------------------------------
def reorganize_floefd(floefd_dir: Path):
    tmp_dir = floefd_dir.parent / "_floefd_tmp"
    print(f"\n[floefd] {floefd_dir.relative_to(RAW_DIR)}")

    moves = []
    for platform_dir in sorted(floefd_dir.iterdir()):
        if not platform_dir.is_dir():
            continue
        for version_dir in sorted(platform_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            for pdf in sorted(version_dir.iterdir()):
                if pdf.is_file() and pdf.suffix.lower() == ".pdf":
                    dst = floefd_dir / version_dir.name / platform_dir.name / pdf.name
                    moves.append((pdf, dst))

    for src, dst in moves:
        move_file(src, dst)

    if not DRY_RUN:
        # Remove now-empty platform dirs
        for platform_dir in sorted(floefd_dir.iterdir()):
            if platform_dir.is_dir() and platform_dir != tmp_dir:
                # Only remove if it contains only empty dirs (no PDFs remain)
                remaining_pdfs = list(platform_dir.rglob("*.pdf"))
                if not remaining_pdfs:
                    shutil.rmtree(str(platform_dir))
                    print(f"  [rm] {platform_dir.relative_to(RAW_DIR)}/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if DRY_RUN:
        print("=== DRY RUN — no files will be moved ===\n")
    else:
        print("=== REORGANIZING data/raw/ ===\n")

    altair_dir   = RAW_DIR / "altair"
    siemens_dir  = RAW_DIR / "siemens-cfd"

    # Flat Altair product dirs
    flat_altair = [
        "hyperworks", "connectme", "electronics", "feko", "flux",
        "hypermesh-cfd", "activate-libs", "physicsai", "simlab",
        "studio", "twin-activate", "license",
    ]
    for name in flat_altair:
        d = altair_dir / name
        if d.exists():
            reorganize_flat(d)
        else:
            print(f"  [skip] {name} not found")

    # Inspire sub-products
    inspire_dir = altair_dir / "inspire"
    if inspire_dir.exists():
        reorganize_inspire(inspire_dir)

    # FLOEFD
    floefd_dir = siemens_dir / "floefd"
    if floefd_dir.exists():
        reorganize_floefd(floefd_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
