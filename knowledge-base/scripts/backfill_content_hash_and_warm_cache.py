#!/usr/bin/env python3
"""
Backfill content_hash for UnifiedTweet and SubcategorySynthesis and warm render cache.

Usage:
  PYTHONPATH="/path/to/repo" ./venv/bin/python scripts/backfill_content_hash_and_warm_cache.py --limit 1000
"""
import argparse
import hashlib
from typing import Optional

from knowledge_base_agent.web import app
from knowledge_base_agent.models import db, UnifiedTweet, SubcategorySynthesis, RenderCache
import markdown


def sha256_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    s = text.strip()
    if not s:
        return None
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def backfill(limit: Optional[int]):
    with app.app_context():
        changed = 0
        warmed = 0

        # UnifiedTweet
        q = db.session.query(UnifiedTweet)
        if isinstance(limit, int) and limit > 0:
            q = q.limit(limit)
        for ut in q.all():
            ch = sha256_text(ut.markdown_content)
            if ch and ut.content_hash != ch:
                ut.content_hash = ch
                changed += 1
            # Warm render cache
            if ch:
                rc = db.session.query(RenderCache).filter_by(document_type='kb_item', document_id=ut.id, content_hash=ch).first()
                if not rc:
                    html = markdown.markdown(ut.markdown_content or "", extensions=['extra', 'codehilite'])
                    db.session.add(RenderCache(document_type='kb_item', document_id=ut.id, content_hash=ch, html=html))
                    warmed += 1

        # Synthesis
        q2 = db.session.query(SubcategorySynthesis)
        if isinstance(limit, int) and limit > 0:
            q2 = q2.limit(limit)
        for syn in q2.all():
            ch = sha256_text(syn.synthesis_content)
            if ch and syn.content_hash != ch:
                syn.content_hash = ch
                changed += 1
            # Warm render cache
            if ch:
                rc = db.session.query(RenderCache).filter_by(document_type='synthesis', document_id=syn.id, content_hash=ch).first()
                if not rc:
                    html = markdown.markdown(syn.synthesis_content or "", extensions=['extra', 'codehilite'])
                    db.session.add(RenderCache(document_type='synthesis', document_id=syn.id, content_hash=ch, html=html))
                    warmed += 1

        if changed or warmed:
            db.session.commit()

        return {'content_hash_updated': changed, 'render_cache_warmed': warmed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    result = backfill(args.limit)
    print(result)


if __name__ == '__main__':
    main()





