#!/usr/bin/env python3
"""Export a compact 15MB cloud seed database (15,000 products) suitable for GitHub & Render/Neon."""
import sqlite3
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def export():
    src_path = ROOT / "data/shopee_muse.db"
    dst_path = ROOT / "data/cloud_catalog.db"
    
    if not src_path.exists():
        print(f"Error: {src_path} not found.")
        return
        
    print(f"Exporting compact catalog from {src_path} -> {dst_path}...")
    t0 = time.time()
    
    if dst_path.exists():
        dst_path.unlink()
        
    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dst_path))
    dst.execute("PRAGMA journal_mode = OFF")
    dst.execute("PRAGMA synchronous = OFF")
    
    # 1. Copy schema
    for sql, in src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"):
        dst.execute(sql)
    for sql, in src.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL AND sql NOT LIKE '%sqlite_autoindex%'"):
        try:
            dst.execute(sql)
        except Exception:
            pass
            
    # 2. Copy reference tables
    for table in ['categories', 'provinces', 'vouchers', 'users', 'catalog_settings']:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if rows:
            placeholders = ','.join('?' for _ in rows[0])
            dst.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
            print(f"  - Copied {len(rows)} rows from {table}")
            
    # 3. Copy top 15,000 aligned products
    prod_rows = src.execute("SELECT * FROM products WHERE id <= 15000").fetchall()
    placeholders = ','.join('?' for _ in prod_rows[0])
    dst.executemany(f"INSERT INTO products VALUES ({placeholders})", prod_rows)
    print(f"  - Copied {len(prod_rows):,} products")
    
    # 4. Copy user behavior histories for demo users
    hist_rows = src.execute("SELECT * FROM user_behavior_history WHERE product_id <= 15000 OR product_id IS NULL").fetchall()
    if hist_rows:
        placeholders = ','.join('?' for _ in hist_rows[0])
        dst.executemany(f"INSERT INTO user_behavior_history VALUES ({placeholders})", hist_rows)
        print(f"  - Copied {len(hist_rows):,} behavior records")

    # 5. Copy muse_item_features for these products
    item_feat = src.execute("SELECT * FROM muse_item_features WHERE raw_item_id IN (SELECT raw_item_id FROM products WHERE id <= 15000)").fetchall()
    if item_feat:
        placeholders = ','.join('?' for _ in item_feat[0])
        dst.executemany(f"INSERT INTO muse_item_features VALUES ({placeholders})", item_feat)
        print(f"  - Copied {len(item_feat):,} MUSE item feature vectors")

    # 6. Copy muse_user_features
    user_feat = src.execute("SELECT * FROM muse_user_features").fetchall()
    if user_feat:
        placeholders = ','.join('?' for _ in user_feat[0])
        dst.executemany(f"INSERT INTO muse_user_features VALUES ({placeholders})", user_feat)
        print(f"  - Copied {len(user_feat):,} MUSE user feature vectors")

    dst.commit()
    dst.close()
    src.close()
    
    size_mb = dst_path.stat().st_size / (1024 * 1024)
    print(f"🎉 Done in {time.time() - t0:.2f}s! Compact database size: {size_mb:.2f} MB ({dst_path})")

if __name__ == "__main__":
    export()
