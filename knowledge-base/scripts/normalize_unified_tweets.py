#!/usr/bin/env python3
"""
Normalize UnifiedTweet rows to modern format without data loss.

- Promote legacy kb_content -> markdown_content where missing
- Ensure kb_media_paths and media_files are JSON lists
- Copy display_title -> kb_display_title if kb_display_title is missing

Usage:
  ./venv/bin/python scripts/normalize_unified_tweets.py --dry-run --limit 100
  ./venv/bin/python scripts/normalize_unified_tweets.py --apply --limit 1000
"""

from __future__ import annotations

import argparse
import json
from typing import List

# Initialize app and DB
from knowledge_base_agent.web import app  # creates app and initializes DB
from knowledge_base_agent.models import db, UnifiedTweet


def normalize(limit: int | None, dry_run: bool) -> dict:
    with app.app_context():
        q = db.session.query(UnifiedTweet)
        if isinstance(limit, int) and limit > 0:
            q = q.limit(limit)
        rows: List[UnifiedTweet] = q.all()

        updated = 0
        changes = []

        for ut in rows:
            actions = []

            # 1) Promote kb_content -> markdown_content if markdown_content is empty
            if (not getattr(ut, 'markdown_content', None)) and getattr(ut, 'kb_content', None):
                actions.append('promote_kb_content_to_markdown_content')
                if not dry_run:
                    ut.markdown_content = ut.kb_content

            # 2) Ensure kb_media_paths is a list
            if isinstance(ut.kb_media_paths, str):
                actions.append('parse_kb_media_paths_string_to_list')
                if not dry_run:
                    try:
                        parsed = json.loads(ut.kb_media_paths)
                        ut.kb_media_paths = parsed if isinstance(parsed, list) else []
                    except Exception:
                        ut.kb_media_paths = []

            # 3) Ensure media_files is a list
            if isinstance(ut.media_files, str):
                actions.append('parse_media_files_string_to_list')
                if not dry_run:
                    try:
                        parsed = json.loads(ut.media_files)
                        ut.media_files = parsed if isinstance(parsed, list) else []
                    except Exception:
                        ut.media_files = []

            # 4) Prefer kb_display_title, else copy from display_title if present
            if not ut.kb_display_title and ut.display_title:
                actions.append('copy_display_title_to_kb_display_title')
                if not dry_run:
                    ut.kb_display_title = ut.display_title

            if actions:
                changes.append({'id': ut.id, 'tweet_id': ut.tweet_id, 'actions': actions})
                if not dry_run:
                    updated += 1

        if not dry_run and updated:
            db.session.commit()

        return {'updated': updated, 'changes': changes}


def main() -> None:
    parser = argparse.ArgumentParser(description='Normalize UnifiedTweet rows to modern format.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true', help='Report what would change without writing')
    group.add_argument('--apply', action='store_true', help='Apply changes to the database')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of rows to process')
    args = parser.parse_args()

    result = normalize(limit=args.limit, dry_run=args.dry_run)
    print(json.dumps({'success': True, 'dry_run': args.dry_run, **result}, indent=2))


if __name__ == '__main__':
    main()



