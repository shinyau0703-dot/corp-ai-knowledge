import os
from pathlib import Path

# Project root = the directory that contains the backend/ folder
PROJECT_ROOT = Path(__file__).parent.parent
DATA_ROOT = PROJECT_ROOT / "data"

RAW_DIR = DATA_ROOT / "raw"
CHUNKS_DIR = DATA_ROOT / "chunks"
CHUNKS_SMALL_DIR = CHUNKS_DIR / "small"
CHUNKS_MEDIUM_DIR = CHUNKS_DIR / "medium"

VECTOR_STORE_DIR = DATA_ROOT / "vector_store"
VECTOR_SMALL_DIR = VECTOR_STORE_DIR / "small"
VECTOR_MEDIUM_DIR = VECTOR_STORE_DIR / "medium"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

PRODUCT_LABELS = {
    "activate-libs": "Activate Libraries", "connectme": "ConnectMe",
    "electronics": "Electronics", "feko": "Feko", "flux": "Flux / FluxMotor",
    "hypermesh-cfd": "HyperMesh CFD", "hyperworks": "HyperWorks",
    "cast": "Cast", "compose": "Compose", "extrude": "Extrude",
    "form": "Form", "inspire": "Inspire", "mold": "Mold", "polyfoam": "PolyFoam",
    "license": "License Management", "pbs": "PBS Professional",
    "physicsai": "PhysicsAI", "simlab": "SimLab", "studio": "Studio",
    "twin-activate": "Twin Activate", "floefd": "FLOEFD",
    "flotherm": "Flotherm", "star-ccm+": "STAR-CCM+",
}

VENDOR_LABELS = {"altair": "Altair", "siemens-cfd": "Siemens CFD"}
