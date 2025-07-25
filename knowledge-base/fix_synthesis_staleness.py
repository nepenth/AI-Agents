#!/usr/bin/env python3
"""
Fix synthesis staleness issues
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
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== FIXING SYNTHESIS STALENESS ISSUES ===\n")
    
    # Get all stale syntheses
    cursor.execute("SELECT * FROM subcategory_synthesis WHERE is_stale = 1 OR needs_regeneration = 1")
    stale_syntheses = cursor.fetchall()
    
    print(f"📊 Found {len(stale_syntheses)} stale synthesis documents")
    
    fixed_count = 0
    
    for synthesis in stale_syntheses:
        print(f"\n🔍 Checking synthesis: {synthesis['main_category']}/{synthesis['sub_category'] or 'MAIN'}")
        
        if synthesis['sub_category'] is None:
            # Main category synthesis - check if subcategory syntheses are newer
            cursor.execute("""
                SELECT MAX(last_updated) as latest_sub_update
                FROM subcategory_synthesis 
                WHERE main_category = ? AND sub_category IS NOT NULL
            """, (synthesis['main_category'],))
            
            result = cursor.fetchone()
            latest_sub_update = result['latest_sub_update']
            
            if latest_sub_update and synthesis['last_updated']:
                try:
                    synthesis_time = datetime.fromisoformat(synthesis['last_updated'].replace('Z', '+00:00'))
                    sub_time = datetime.fromisoformat(latest_sub_update.replace('Z', '+00:00'))
                    
                    if sub_time <= synthesis_time:
                        # Main category synthesis is actually up to date
                        print(f"  ✅ Main category synthesis is up to date - clearing stale flag")
                        cursor.execute("""
                            UPDATE subcategory_synthesis 
                            SET is_stale = 0, needs_regeneration = 0 
                            WHERE id = ?
                        """, (synthesis['id'],))
                        fixed_count += 1
                    else:
                        print(f"  ⚠️  Main category synthesis is genuinely stale")
                        print(f"      Synthesis: {synthesis['last_updated']}")
                        print(f"      Latest sub: {latest_sub_update}")
                except Exception as e:
                    print(f"  ❌ Error parsing dates: {e}")
            else:
                print(f"  ⚠️  Missing timestamp data")
        else:
            # Subcategory synthesis - check if KB items are newer
            cursor.execute("""
                SELECT COUNT(*) as count, MAX(last_updated) as latest_update 
                FROM knowledge_base_item 
                WHERE main_category = ? AND sub_category = ?
            """, (synthesis['main_category'], synthesis['sub_category']))
            
            kb_result = cursor.fetchone()
            current_item_count = kb_result['count']
            latest_kb_update = kb_result['latest_update']
            
            # Check dependency consistency
            if synthesis['dependency_item_ids']:
                try:
                    dep_ids = json.loads(synthesis['dependency_item_ids'])
                    cursor.execute("""
                        SELECT id FROM knowledge_base_item 
                        WHERE main_category = ? AND sub_category = ?
                    """, (synthesis['main_category'], synthesis['sub_category']))
                    
                    current_kb_ids = [row['id'] for row in cursor.fetchall()]
                    
                    missing_deps = set(dep_ids) - set(current_kb_ids)
                    new_items = set(current_kb_ids) - set(dep_ids)
                    
                    if not missing_deps and not new_items:
                        # Dependencies are consistent - check timestamps
                        if latest_kb_update and synthesis['last_updated']:
                            try:
                                synthesis_time = datetime.fromisoformat(synthesis['last_updated'].replace('Z', '+00:00'))
                                kb_time = datetime.fromisoformat(latest_kb_update.replace('Z', '+00:00'))
                                
                                if kb_time <= synthesis_time:
                                    # Synthesis is actually up to date
                                    print(f"  ✅ Subcategory synthesis is up to date - clearing stale flag")
                                    cursor.execute("""
                                        UPDATE subcategory_synthesis 
                                        SET is_stale = 0, needs_regeneration = 0 
                                        WHERE id = ?
                                    """, (synthesis['id'],))
                                    fixed_count += 1
                                else:
                                    print(f"  ⚠️  Subcategory synthesis is genuinely stale")
                                    print(f"      Synthesis: {synthesis['last_updated']}")
                                    print(f"      Latest KB: {latest_kb_update}")
                            except Exception as e:
                                print(f"  ❌ Error parsing dates: {e}")
                        else:
                            print(f"  ⚠️  Missing timestamp data")
                    else:
                        print(f"  ⚠️  Dependencies have changed:")
                        if missing_deps:
                            print(f"      Missing: {len(missing_deps)} items")
                        if new_items:
                            print(f"      New: {len(new_items)} items")
                            
                except Exception as e:
                    print(f"  ❌ Error checking dependencies: {e}")
    
    # Commit changes
    conn.commit()
    
    print(f"\n📊 SUMMARY:")
    print(f"  - Fixed {fixed_count} incorrectly marked stale syntheses")
    print(f"  - {len(stale_syntheses) - fixed_count} syntheses remain stale")
    
    # Check remaining stale syntheses
    cursor.execute("SELECT * FROM subcategory_synthesis WHERE is_stale = 1 OR needs_regeneration = 1")
    remaining_stale = cursor.fetchall()
    
    if remaining_stale:
        print(f"\n⚠️  REMAINING STALE SYNTHESES ({len(remaining_stale)}):")
        for s in remaining_stale:
            print(f"  - {s['main_category']}/{s['sub_category'] or 'MAIN'}")
    else:
        print(f"\n✅ All synthesis staleness issues have been resolved!")
    
    # Show new subcategories that still need synthesis
    cursor.execute("""
        SELECT main_category, sub_category, COUNT(*) as item_count
        FROM knowledge_base_item 
        GROUP BY main_category, sub_category
        HAVING COUNT(*) >= 2
    """)
    
    kb_subcategories = cursor.fetchall()
    
    cursor.execute("SELECT main_category, sub_category FROM subcategory_synthesis WHERE sub_category IS NOT NULL")
    existing_syntheses = {(row['main_category'], row['sub_category']) for row in cursor.fetchall()}
    
    new_subcategories = []
    for kb_sub in kb_subcategories:
        key = (kb_sub['main_category'], kb_sub['sub_category'])
        if key not in existing_syntheses:
            new_subcategories.append(kb_sub)
    
    if new_subcategories:
        print(f"\n🆕 NEW SUBCATEGORIES STILL NEEDING SYNTHESIS ({len(new_subcategories)}):")
        for sub in new_subcategories:
            print(f"  - {sub['main_category']}/{sub['sub_category']} ({sub['item_count']} items)")
        
        print(f"\n💡 These will be created on the next agent run.")
    else:
        print(f"\n✅ No new subcategories need synthesis documents!")
    
    conn.close()
    print(f"\n✅ Staleness fix complete!")

if __name__ == "__main__":
    main()