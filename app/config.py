"""Portable runtime settings. Demo-only capabilities are explicitly gated."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data/shopee_muse.db")))
DATASET_DIR = Path(os.getenv("MUSE_DATASET_DIR", str(ROOT / "data")))
CHECKPOINT_DIR = Path(os.getenv("MUSE_CHECKPOINT_DIR", str(ROOT / "checkpoints")))
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "false").lower() == "true"
SESSION_SECONDS = 60 * 60 * 24 * 7
FREE_SHIPPING_THRESHOLD = 150_000
