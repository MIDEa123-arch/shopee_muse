"""Fast sync from PostgreSQL to SQLite mirror with WAL and synchronous=OFF."""
import sqlite3
import psycopg2
import time

def main():
    start = time.time()
    pg_conn = psycopg2.connect("dbname=shopee_muse user=midea")
    pg_cur = pg_conn.cursor("stream_cur")

    sqlite_conn = sqlite3.connect("data/shopee_muse.db", timeout=60)
    sqlite_cur = sqlite_conn.cursor()

    sqlite_cur.execute("PRAGMA synchronous = OFF;")
    sqlite_cur.execute("PRAGMA journal_mode = WAL;")
    sqlite_cur.execute("PRAGMA cache_size = 100000;")

    print("Loading existing raw_item_ids from SQLite...")
    sqlite_cur.execute("SELECT raw_item_id FROM products;")
    existing_ids = set(r[0] for r in sqlite_cur.fetchall())
    print(f"Loaded {len(existing_ids):,} existing IDs from SQLite.")

    print("Streaming products from PostgreSQL...")
    pg_cur.itersize = 25000
    pg_cur.execute("""
        SELECT raw_item_id, name, category_id, price, original_price, discount_percent,
               stock, sold_count, rating_star, rating_count, image_url, province_id,
               shop_name, is_mall, is_freeship, description, catalog_source,
               source_feature_complete, source_category_id, source_city_id, source_province_id,
               brand, images_json, bought_together_json
        FROM products
    """)

    sql = """
        INSERT INTO products (
            raw_item_id, name, category_id, price, original_price, discount_percent,
            stock, sold_count, rating_star, rating_count, image_url, province_id,
            shop_name, is_mall, is_freeship, description, catalog_source,
            source_feature_complete, source_category_id, source_city_id, source_province_id,
            brand, images_json, bought_together_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    inserted = 0
    batch = []
    for row in pg_cur:
        if row[0] in existing_ids:
            continue
        existing_ids.add(row[0])
        batch.append(row)
        if len(batch) >= 25000:
            sqlite_cur.executemany(sql, batch)
            sqlite_conn.commit()
            inserted += len(batch)
            print(f"Synced {inserted:,} new products to SQLite... ({time.time() - start:.1f}s)")
            batch = []

    if batch:
        sqlite_cur.executemany(sql, batch)
        sqlite_conn.commit()
        inserted += len(batch)

    print(f"Sync complete in {time.time() - start:.1f}s! Total newly inserted: {inserted:,}")

    sqlite_cur.execute("SELECT count(*) FROM products;")
    total_sql = sqlite_cur.fetchone()[0]
    print(f"SQLite total products count: {total_sql:,}")

    print("Ensuring SQLite composite indexes...")
    sqlite_cur.execute("CREATE INDEX IF NOT EXISTS idx_products_cat_sold ON products(category_id, sold_count DESC);")
    sqlite_cur.execute("CREATE INDEX IF NOT EXISTS idx_products_cat_rating ON products(category_id, rating_star DESC);")
    sqlite_cur.execute("CREATE INDEX IF NOT EXISTS idx_products_sold_count ON products(sold_count DESC);")
    sqlite_cur.execute("CREATE INDEX IF NOT EXISTS idx_products_cat_price ON products(category_id, price ASC);")
    sqlite_cur.execute("CREATE INDEX IF NOT EXISTS idx_products_raw_id ON products(raw_item_id);")
    sqlite_conn.commit()

    sqlite_cur.execute("PRAGMA synchronous = NORMAL;")
    sqlite_conn.close()
    pg_conn.close()
    print("All mirrors updated successfully!")

if __name__ == "__main__":
    main()
