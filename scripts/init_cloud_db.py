#!/usr/bin/env python3
"""Initialize cloud database for Render deployment (supports both SQLite and Neon PostgreSQL)."""
import os
import sys
import time
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def init_sqlite_cloud():
    db_path = ROOT / "data/shopee_muse.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If database already exists and has products, we're ready
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cnt = conn.execute("SELECT count(*) FROM products").fetchone()[0]
            conn.close()
            if cnt > 1000:
                print(f"✅ SQLite database already contains {cnt:,} products at {db_path}")
                return
        except Exception:
            pass

    # If compact cloud seed exists, copy it in 0.05s
    cloud_seed = ROOT / "data/cloud_catalog.db"
    if cloud_seed.exists():
        import shutil
        shutil.copyfile(str(cloud_seed), str(db_path))
        print(f"✅ Copied cloud seed catalog ({cloud_seed.stat().st_size / 1024 / 1024:.1f} MB) -> {db_path}")
        return
    
    # Ensure tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS catalog_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_presentations (
          product_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          category_slug TEXT NOT NULL, category_name TEXT NOT NULL, image_url TEXT NOT NULL,
          images_json TEXT NOT NULL, brand TEXT NOT NULL, description TEXT NOT NULL,
          price INTEGER NOT NULL, original_price INTEGER NOT NULL, shop_name TEXT NOT NULL,
          template_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS addresses (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
          recipient_name TEXT NOT NULL, phone TEXT NOT NULL, province_id INTEGER NOT NULL,
          detail TEXT NOT NULL, label TEXT NOT NULL DEFAULT 'Nhà riêng', is_default INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS reset_challenges (
          id TEXT PRIMARY KEY, user_id INTEGER, code_hash TEXT NOT NULL,
          expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS auth_attempts (key TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS wishlist (
          user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
          PRIMARY KEY(user_id,product_id));
        CREATE TABLE IF NOT EXISTS reviews (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
          product_id INTEGER NOT NULL, rating INTEGER NOT NULL,
          content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS muse_user_features (
          user_id INTEGER PRIMARY KEY, features_json TEXT NOT NULL, source TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS muse_item_features (
          raw_item_id INTEGER PRIMARY KEY, features_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_events (
          id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT NOT NULL,
          entity_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    
    conn.close()
    print(f"✅ Cloud database initialized successfully in {time.time() - t0:.2f}s!")


def main():
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres"):
        print(f"Connecting to remote PostgreSQL (Neon)...")
        # In case user configures Neon
        from scripts.sync_pg_to_sqlite import main as sync_main
        # Can sync or seed
    else:
        init_sqlite_cloud()

if __name__ == "__main__":
    main()
