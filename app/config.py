"""Portable runtime settings. Demo-only capabilities are explicitly gated."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def _get_db_path() -> Path:
    env_p = os.getenv("DATABASE_PATH")
    if env_p:
        return Path(env_p)
    full = ROOT / "data/shopee_muse.db"
    if full.exists() and full.stat().st_size > 1024 * 1024:
        return full
    cloud = ROOT / "data/cloud_catalog.db"
    if cloud.exists():
        return cloud
    return full

DB_PATH = _get_db_path()
DATASET_DIR = Path(os.getenv("MUSE_DATASET_DIR", str(ROOT / "data")))
CHECKPOINT_DIR = Path(os.getenv("MUSE_CHECKPOINT_DIR", str(ROOT / "checkpoints")))
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() == "true"
SESSION_SECONDS = 60 * 60 * 24 * 7
FREE_SHIPPING_THRESHOLD = 150_000
