#!/usr/bin/env python3
"""
SQLite modernization migration:
- Add content_hash columns to unified_tweet and subcategory_synthesis
- Create render_cache table with unique key (document_type, document_id, content_hash)
- Create indexes to support lookups

Run with backend stopped:
  PYTHONPATH="/path/to/repo" ./venv/bin/python scripts/sqlite_migrate_modernization.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / 'instance' / 'knowledge_base.db'


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def table_exists(cur, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.isolation_level = None  # autocommit disabled; using explicit BEGIN
    cur = conn.cursor()

    try:
        cur.execute("BEGIN")

        # 1) Add content_hash columns if missing
        if not column_exists(cur, 'unified_tweet', 'content_hash'):
            cur.execute("ALTER TABLE unified_tweet ADD COLUMN content_hash TEXT")
        if not column_exists(cur, 'subcategory_synthesis', 'content_hash'):
            cur.execute("ALTER TABLE subcategory_synthesis ADD COLUMN content_hash TEXT")

        # 2) Create render_cache table if missing
        if not table_exists(cur, 'render_cache'):
            cur.execute(
                """
                CREATE TABLE render_cache (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  document_type TEXT NOT NULL,
                  document_id INTEGER NOT NULL,
                  content_hash TEXT NOT NULL,
                  html TEXT NOT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(document_type, document_id, content_hash)
                )
                """
            )

        # 3) Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_unified_tweet_content_hash ON unified_tweet(content_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subcategory_synthesis_content_hash ON subcategory_synthesis(content_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_render_cache_lookup ON render_cache(document_type, document_id, content_hash)")

        conn.commit()
        print({
            'success': True,
            'db_path': str(DB_PATH),
            'actions': ['add content_hash columns', 'create render_cache', 'create indexes']
        })
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()





