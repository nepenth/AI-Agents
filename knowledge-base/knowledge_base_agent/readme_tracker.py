"""
README Generation Dependency Tracker

This module tracks dependencies for README generation and determines when it needs to be regenerated
based on changes to Knowledge Base items, similar to how synthesis generation tracking works.
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .models import db, KnowledgeBaseItem, SubcategorySynthesis


class ReadmeDependencyTracker:
    """Tracks dependencies for README generation and determines staleness."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def analyze_readme_staleness(self) -> Dict[str, Any]:
        """
        Analyze whether the README needs regeneration based on KB item changes.
        Returns analysis similar to synthesis staleness analysis.
        """
        self.logger.info("Analyzing README staleness...")
        
        readme_path = self.config.knowledge_base_dir / "README.md"
        
        analysis = {
            'readme_exists': readme_path.exists(),
            'total_kb_items': 0,
            'readme_last_modified': None,
            'latest_kb_item_update': None,
            'is_stale': False,
            'staleness_reason': None,
            'new_items_since_readme': 0,
            'updated_items_since_readme': 0
        }
        
        # Get README last modified time (timezone-aware)
        if readme_path.exists():
            readme_mtime = datetime.fromtimestamp(readme_path.stat().st_mtime, tz=timezone.utc)
            analysis['readme_last_modified'] = readme_mtime.isoformat()
        else:
            self.logger.info("README.md does not exist - needs generation")
            analysis['is_stale'] = True
            analysis['staleness_reason'] = 'missing'
            return analysis
        
        # Get all KB items and synthesis documents
        all_kb_items = KnowledgeBaseItem.query.all()
        all_syntheses = SubcategorySynthesis.query.all()
        
        analysis['total_kb_items'] = len(all_kb_items)
        analysis['total_syntheses'] = len(all_syntheses)
        analysis['total_content'] = len(all_kb_items) + len(all_syntheses)
        
        if not all_kb_items and not all_syntheses:
            self.logger.info("No KB items or synthesis documents found - README up to date")
            return analysis
        
        # Find latest update across both KB items and synthesis documents
        latest_update = None
        
        # Check KB items
        for item in all_kb_items:
            if item.last_updated:
                # Ensure datetime is timezone-aware
                item_update = item.last_updated
                if item_update.tzinfo is None:
                    # If timezone-naive, assume UTC
                    item_update = item_update.replace(tzinfo=timezone.utc)
                
                if latest_update is None or item_update > latest_update:
                    latest_update = item_update
        
        # Check synthesis documents
        for synthesis in all_syntheses:
            if synthesis.last_updated:
                # Ensure datetime is timezone-aware
                synthesis_update = synthesis.last_updated
                if synthesis_update.tzinfo is None:
                    # If timezone-naive, assume UTC
                    synthesis_update = synthesis_update.replace(tzinfo=timezone.utc)
                
                if latest_update is None or synthesis_update > latest_update:
                    latest_update = synthesis_update
        
        if latest_update:
            analysis['latest_content_update'] = latest_update.isoformat()
            # Keep the old key for backwards compatibility
            analysis['latest_kb_item_update'] = latest_update.isoformat()
            
            # Compare with README modification time (both should now be timezone-aware)
            if latest_update > readme_mtime:
                analysis['is_stale'] = True
                analysis['staleness_reason'] = 'content_updated_after_readme'
                
                # Count KB items newer than README
                for item in all_kb_items:
                    # Ensure item datetimes are timezone-aware for comparison
                    item_created = item.created_at
                    item_updated = item.last_updated
                    
                    if item_created and item_created.tzinfo is None:
                        item_created = item_created.replace(tzinfo=timezone.utc)
                    if item_updated and item_updated.tzinfo is None:
                        item_updated = item_updated.replace(tzinfo=timezone.utc)
                    
                    if item_created and item_created > readme_mtime:
                        analysis['new_items_since_readme'] += 1
                    elif item_updated and item_updated > readme_mtime:
                        analysis['updated_items_since_readme'] += 1
                
                # Count synthesis documents newer than README
                analysis['new_syntheses_since_readme'] = 0
                analysis['updated_syntheses_since_readme'] = 0
                
                for synthesis in all_syntheses:
                    # Ensure synthesis datetimes are timezone-aware for comparison
                    synthesis_created = synthesis.created_at
                    synthesis_updated = synthesis.last_updated
                    
                    if synthesis_created and synthesis_created.tzinfo is None:
                        synthesis_created = synthesis_created.replace(tzinfo=timezone.utc)
                    if synthesis_updated and synthesis_updated.tzinfo is None:
                        synthesis_updated = synthesis_updated.replace(tzinfo=timezone.utc)
                    
                    if synthesis_created and synthesis_created > readme_mtime:
                        analysis['new_syntheses_since_readme'] += 1
                    elif synthesis_updated and synthesis_updated > readme_mtime:
                        analysis['updated_syntheses_since_readme'] += 1
        
        self.logger.info(f"README staleness analysis: {analysis}")
        return analysis
    
    def needs_regeneration(self, force_regenerate: bool = False) -> bool:
        """
        Determine if README needs regeneration.
        
        Args:
            force_regenerate: If True, always regenerate regardless of staleness
            
        Returns:
            bool: True if README needs regeneration
        """
        if force_regenerate:
            self.logger.info("README regeneration forced")
            return True
            
        analysis = self.analyze_readme_staleness()
        needs_regen = analysis['is_stale']
        
        if needs_regen:
            reason = analysis['staleness_reason']
            self.logger.info(f"README needs regeneration: {reason}")
        else:
            self.logger.info("README is up to date")
            
        return needs_regen
    
    def create_readme_execution_plan(self, force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Create execution plan for README generation similar to PhaseExecutionHelper.
        
        Args:
            force_regenerate: If True, force regeneration regardless of staleness
            
        Returns:
            Dict with execution plan details
        """
        # Force regeneration overrides all staleness analysis
        if force_regenerate:
            self.logger.info("README regeneration forced - bypassing staleness analysis")
            # Get basic analysis for item counts but force regeneration
            analysis = self.analyze_readme_staleness()
            return {
                'needs_generation': True,
                'skip_reason': None,
                'analysis': analysis,
                'total_kb_items': analysis['total_kb_items'],
                'force_regenerate': True
            }
        
        # Normal staleness-based analysis
        analysis = self.analyze_readme_staleness()
        needs_regen = analysis['is_stale']
        
        plan = {
            'needs_generation': needs_regen,
            'skip_reason': None if needs_regen else 'up_to_date',
            'analysis': analysis,
            'total_kb_items': analysis['total_kb_items'],
            'force_regenerate': False
        }
        
        if not needs_regen:
            plan['skip_reason'] = 'up_to_date'
            if analysis['total_kb_items'] == 0:
                plan['skip_reason'] = 'no_kb_items'
        
        self.logger.info(
            f"README execution plan: needs_generation={needs_regen}, "
            f"total_kb_items={plan['total_kb_items']}, "
            f"skip_reason={plan['skip_reason']}, "
            f"force_regenerate={force_regenerate}"
        )
        
        return plan
    
    def get_kb_items_summary(self) -> Dict[str, Any]:
        """
        Get summary information about KB items for README generation.
        
        Returns:
            Dict with KB items summary
        """
        all_items = KnowledgeBaseItem.query.all()
        
        summary = {
            'total_items': len(all_items),
            'categories': {},
            'recent_items': [],
            'total_main_cats': 0,
            'total_subcats': 0
        }
        
        # Group by categories
        for item in all_items:
            main_cat = item.main_category or 'Uncategorized'
            sub_cat = item.sub_category or 'General'
            
            if main_cat not in summary['categories']:
                summary['categories'][main_cat] = {}
            if sub_cat not in summary['categories'][main_cat]:
                summary['categories'][main_cat][sub_cat] = []
                
            summary['categories'][main_cat][sub_cat].append({
                'id': item.id,
                'item_name': item.item_name,
                'file_path': item.file_path,
                'updated_at': item.last_updated.isoformat() if item.last_updated else None,
                'source_url': item.source_url
            })
        
        # Calculate totals
        summary['total_main_cats'] = len(summary['categories'])
        summary['total_subcats'] = sum(
            len(subcats) for subcats in summary['categories'].values()
        )
        
        # Get recent items (last 5)
        recent_items = sorted(
            [item for item in all_items if item.last_updated],
            key=lambda x: x.last_updated,
            reverse=True
        )[:5]
        
        summary['recent_items'] = [
            {
                'id': item.id,
                'item_name': item.item_name,
                'main_category': item.main_category,
                'sub_category': item.sub_category,
                'file_path': item.file_path,
                'updated_at': item.last_updated.isoformat() if item.last_updated else None,
                'source_url': item.source_url
            }
            for item in recent_items
        ]
        
        return summary 