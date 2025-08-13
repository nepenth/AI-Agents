#!/usr/bin/env python3
"""
SQLite FTS5 migration for Knowledge Base and Synthesis search.

Creates FTS5 virtual tables and triggers to keep them in sync,
and performs an initial population from existing data.

Run with backend stopped:
  ./venv/bin/python scripts/sqlite_migrate_fts.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / 'instance' / 'knowledge_base.db'


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.isolation_level = None
    cur = conn.cursor()

    try:
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("BEGIN")

        # Recreate FTS tables from scratch to avoid issues with contentless FTS5 bulk delete
        # (Contentless FTS5 tables cannot be cleared using DELETE statements.)
        cur.execute("DROP TABLE IF EXISTS kb_item_fts")
        cur.execute("DROP TABLE IF EXISTS synthesis_fts")

        # Create FTS tables
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS kb_item_fts USING fts5(
              id UNINDEXED,
              title,
              content,
              main_category,
              sub_category,
              combined,
              content=''
            )
            """
        )

        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS synthesis_fts USING fts5(
              id UNINDEXED,
              title,
              content,
              main_category,
              sub_category,
              combined,
              content=''
            )
            """
        )

        # Triggers for unified_tweet
        cur.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS kb_item_fts_ai AFTER INSERT ON unified_tweet BEGIN
              INSERT INTO kb_item_fts(id,title,content,main_category,sub_category,combined)
              VALUES (new.id,
                      COALESCE(new.kb_display_title, new.kb_item_name, ''),
                      COALESCE(new.markdown_content, ''),
                      COALESCE(new.main_category, ''),
                      COALESCE(new.sub_category, ''),
                      printf('%s %s %s %s', COALESCE(new.kb_display_title, new.kb_item_name, ''), COALESCE(new.markdown_content, ''), COALESCE(new.main_category, ''), COALESCE(new.sub_category, '')));
            END;

            CREATE TRIGGER IF NOT EXISTS kb_item_fts_au AFTER UPDATE ON unified_tweet BEGIN
              UPDATE kb_item_fts SET
                title=COALESCE(new.kb_display_title, new.kb_item_name, ''),
                content=COALESCE(new.markdown_content, ''),
                main_category=COALESCE(new.main_category, ''),
                sub_category=COALESCE(new.sub_category, ''),
                combined=printf('%s %s %s %s', COALESCE(new.kb_display_title, new.kb_item_name, ''), COALESCE(new.markdown_content, ''), COALESCE(new.main_category, ''), COALESCE(new.sub_category, ''))
              WHERE id=new.id;
            END;

            CREATE TRIGGER IF NOT EXISTS kb_item_fts_ad AFTER DELETE ON unified_tweet BEGIN
              DELETE FROM kb_item_fts WHERE id=old.id;
            END;
            """
        )

        # Triggers for subcategory_synthesis
        cur.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS synthesis_fts_ai AFTER INSERT ON subcategory_synthesis BEGIN
              INSERT INTO synthesis_fts(id,title,content,main_category,sub_category,combined)
              VALUES (new.id,
                      COALESCE(new.synthesis_title, ''),
                      COALESCE(new.synthesis_content, ''),
                      COALESCE(new.main_category, ''),
                      COALESCE(new.sub_category, ''),
                      printf('%s %s %s %s', COALESCE(new.synthesis_title, ''), COALESCE(new.synthesis_content, ''), COALESCE(new.main_category, ''), COALESCE(new.sub_category, '')));
            END;

            CREATE TRIGGER IF NOT EXISTS synthesis_fts_au AFTER UPDATE ON subcategory_synthesis BEGIN
              UPDATE synthesis_fts SET
                title=COALESCE(new.synthesis_title, ''),
                content=COALESCE(new.synthesis_content, ''),
                main_category=COALESCE(new.main_category, ''),
                sub_category=COALESCE(new.sub_category, ''),
                combined=printf('%s %s %s %s', COALESCE(new.synthesis_title, ''), COALESCE(new.synthesis_content, ''), COALESCE(new.main_category, ''), COALESCE(new.sub_category, ''))
              WHERE id=new.id;
            END;

            CREATE TRIGGER IF NOT EXISTS synthesis_fts_ad AFTER DELETE ON subcategory_synthesis BEGIN
              DELETE FROM synthesis_fts WHERE id=old.id;
            END;
            """
        )

        # Initial population
        cur.execute(
            """
            INSERT INTO kb_item_fts(id,title,content,main_category,sub_category,combined)
            SELECT id,
                   COALESCE(kb_display_title, kb_item_name, ''),
                   COALESCE(markdown_content, ''),
                   COALESCE(main_category, ''),
                   COALESCE(sub_category, ''),
                   printf('%s %s %s %s', COALESCE(kb_display_title, kb_item_name, ''), COALESCE(markdown_content, ''), COALESCE(main_category, ''), COALESCE(sub_category, ''))
            FROM unified_tweet
            WHERE kb_item_created=1 AND markdown_content IS NOT NULL
            """
        )

        cur.execute(
            """
            INSERT INTO synthesis_fts(id,title,content,main_category,sub_category,combined)
            SELECT id,
                   COALESCE(synthesis_title, ''),
                   COALESCE(synthesis_content, ''),
                   COALESCE(main_category, ''),
                   COALESCE(sub_category, ''),
                   printf('%s %s %s %s', COALESCE(synthesis_title, ''), COALESCE(synthesis_content, ''), COALESCE(main_category, ''), COALESCE(sub_category, ''))
            FROM subcategory_synthesis
            WHERE synthesis_content IS NOT NULL
            """
        )

        conn.commit()
        print({'success': True, 'db_path': str(DB_PATH)})
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()




