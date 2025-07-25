#!/usr/bin/env python3
"""
Diagnose synthesis staleness issues - simplified version
"""

import sys
import os
import sqlite3
import json
from datetime import datetime

def main():
    # Connect directly to the database
    db_path = "instance/knowledge_base.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()
    
    print("=== SYNTHESIS STALENESS DIAGNOSIS ===\n")
    
    # Get all synthesis documents
    cursor.execute("SELECT * FROM subcategory_synthesis ORDER BY main_category, sub_category")
    syntheses = cursor.fetchall()
    
    print(f"📊 Total synthesis documents: {len(syntheses)}\n")
    
    # Count by type
    subcategory_count = sum(1 for s in syntheses if s['sub_category'] is not None)
    main_category_count = len(syntheses) - subcategory_count
    
    print(f"📈 Synthesis Breakdown:")
    print(f"  - Subcategory syntheses: {subcategory_count}")
    print(f"  - Main category syntheses: {main_category_count}")
    print()
    
    # Count staleness flags
    stale_count = sum(1 for s in syntheses if s['is_stale'])
    needs_regen_count = sum(1 for s in syntheses if s['needs_regeneration'])
    
    print(f"🔍 Staleness Status:")
    print(f"  - Marked as stale: {stale_count}")
    print(f"  - Needs regeneration: {needs_regen_count}")
    print(f"  - Up to date: {len(syntheses) - stale_count - needs_regen_count}")
    print()
    
    # Show detailed synthesis information
    print("📋 DETAILED SYNTHESIS INFORMATION:")
    print("=" * 80)
    
    for i, s in enumerate(syntheses, 1):
        print(f"\n{i}. Synthesis ID: {s['id']}")
        print(f"   Category: {s['main_category']}/{s['sub_category'] or 'MAIN'}")
        print(f"   Title: {s['synthesis_title']}")
        print(f"   Item Count: {s['item_count']}")
        print(f"   Is Stale: {s['is_stale']}")
        print(f"   Needs Regeneration: {s['needs_regeneration']}")
        print(f"   Last Updated: {s['last_updated']}")
        print(f"   Last Item Update: {s['last_item_update']}")
        
        # Show content hash
        if s['content_hash']:
            print(f"   Content Hash: {s['content_hash'][:16]}...")
        else:
            print(f"   Content Hash: None")
        
        # Show dependency IDs
        if s['dependency_item_ids']:
            try:
                dep_ids = json.loads(s['dependency_item_ids'])
                print(f"   Dependencies: {len(dep_ids)} items - {dep_ids[:5]}{'...' if len(dep_ids) > 5 else ''}")
            except:
                print(f"   Dependencies: Invalid JSON - {s['dependency_item_ids'][:50]}...")
        else:
            print(f"   Dependencies: None")
        
        # If it's a subcategory synthesis, check current KB items
        if s['sub_category']:
            cursor.execute("""
                SELECT COUNT(*) as count, MAX(last_updated) as latest_update 
                FROM knowledge_base_item 
                WHERE main_category = ? AND sub_category = ?
            """, (s['main_category'], s['sub_category']))
            
            kb_result = cursor.fetchone()
            current_item_count = kb_result['count']
            latest_kb_update = kb_result['latest_update']
            
            print(f"   Current KB Items: {current_item_count}")
            print(f"   Latest KB Update: {latest_kb_update}")
            
            # Check if KB items are newer than synthesis
            if s['last_updated'] and latest_kb_update:
                synthesis_time = datetime.fromisoformat(s['last_updated'].replace('Z', '+00:00'))
                kb_time = datetime.fromisoformat(latest_kb_update.replace('Z', '+00:00'))
                
                if kb_time > synthesis_time:
                    print(f"   ⚠️  KB items are newer than synthesis!")
                    print(f"      Synthesis: {s['last_updated']}")
                    print(f"      Latest KB: {latest_kb_update}")
            
            # Check dependency consistency
            if s['dependency_item_ids']:
                try:
                    dep_ids = json.loads(s['dependency_item_ids'])
                    cursor.execute("""
                        SELECT id FROM knowledge_base_item 
                        WHERE main_category = ? AND sub_category = ?
                    """, (s['main_category'], s['sub_category']))
                    
                    current_kb_ids = [row['id'] for row in cursor.fetchall()]
                    
                    missing_deps = set(dep_ids) - set(current_kb_ids)
                    new_items = set(current_kb_ids) - set(dep_ids)
                    
                    if missing_deps:
                        print(f"   ⚠️  Missing dependencies: {len(missing_deps)} items")
                    if new_items:
                        print(f"   ⚠️  New items since last synthesis: {len(new_items)} items")
                        print(f"      New item IDs: {list(new_items)[:5]}{'...' if len(new_items) > 5 else ''}")
                    
                    if not missing_deps and not new_items:
                        print(f"   ✅ Dependencies are consistent")
                        
                except Exception as e:
                    print(f"   ❌ Error checking dependencies: {e}")
        
        print("   " + "-" * 70)
    
    # Check for categories that might need new synthesis documents
    print(f"\n🔍 CHECKING FOR NEW CATEGORIES NEEDING SYNTHESIS:")
    
    # Find subcategories with enough items but no synthesis
    cursor.execute("""
        SELECT main_category, sub_category, COUNT(*) as item_count
        FROM knowledge_base_item 
        GROUP BY main_category, sub_category
        HAVING COUNT(*) >= 2
    """)
    
    kb_subcategories = cursor.fetchall()
    existing_syntheses = {(s['main_category'], s['sub_category']) for s in syntheses if s['sub_category']}
    
    new_subcategories = []
    for kb_sub in kb_subcategories:
        key = (kb_sub['main_category'], kb_sub['sub_category'])
        if key not in existing_syntheses:
            new_subcategories.append(kb_sub)
    
    if new_subcategories:
        print(f"🆕 Found {len(new_subcategories)} subcategories needing synthesis:")
        for sub in new_subcategories:
            print(f"  - {sub['main_category']}/{sub['sub_category']} ({sub['item_count']} items)")
    else:
        print("✅ No new subcategories need synthesis")
    
    # Find main categories with enough subcategory syntheses but no main synthesis
    cursor.execute("""
        SELECT main_category, COUNT(*) as synthesis_count
        FROM subcategory_synthesis 
        WHERE sub_category IS NOT NULL
        GROUP BY main_category
        HAVING COUNT(*) >= 2
    """)
    
    main_cats_with_subs = cursor.fetchall()
    existing_main_syntheses = {s['main_category'] for s in syntheses if s['sub_category'] is None}
    
    new_main_categories = []
    for main_cat in main_cats_with_subs:
        if main_cat['main_category'] not in existing_main_syntheses:
            new_main_categories.append(main_cat)
    
    if new_main_categories:
        print(f"🆕 Found {len(new_main_categories)} main categories needing synthesis:")
        for main in new_main_categories:
            print(f"  - {main['main_category']} ({main['synthesis_count']} subcategory syntheses)")
    else:
        print("✅ No new main categories need synthesis")
    
    # Summary of what would be regenerated
    total_needing_generation = (
        stale_count + 
        needs_regen_count + 
        len(new_subcategories) + 
        len(new_main_categories)
    )
    
    print(f"\n📊 SUMMARY:")
    print(f"  - Existing syntheses needing regeneration: {stale_count + needs_regen_count}")
    print(f"  - New subcategories needing synthesis: {len(new_subcategories)}")
    print(f"  - New main categories needing synthesis: {len(new_main_categories)}")
    print(f"  - TOTAL that would be generated: {total_needing_generation}")
    
    if total_needing_generation == 0:
        print(f"\n✅ All synthesis documents appear to be up to date!")
    else:
        print(f"\n⚠️  {total_needing_generation} synthesis documents would be generated on next run")
    
    conn.close()
    print(f"\n✅ Diagnosis complete!")

if __name__ == "__main__":
    main()