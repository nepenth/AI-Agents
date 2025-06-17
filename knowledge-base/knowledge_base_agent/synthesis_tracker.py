"""
Synthesis Dependency Tracker Module

This module handles dependency tracking and staleness detection for synthesis documents,
following our first principles architecture:
1. State-driven validation (like StateManager's validation phases)
2. Phase-based execution planning (like PhaseExecutionHelper)
3. Database-driven tracking (like our models)
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any

from sqlalchemy import and_, func

from .config import Config
from .models import db, KnowledgeBaseItem, SubcategorySynthesis
from .custom_types import Synthesis as SynthesisType


class SynthesisDependencyTracker:
    """
    Tracks synthesis document dependencies and staleness following our architecture principles.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def analyze_synthesis_staleness(self) -> Dict[str, Any]:
        """
        Analyze staleness across all synthesis documents.
        Returns comprehensive analysis similar to PhaseExecutionHelper.analyze_processing_state()
        """
        self.logger.info("Analyzing synthesis document staleness...")
        
        # Get all synthesis documents
        all_syntheses = SubcategorySynthesis.query.all()
        
        analysis = {
            'total_syntheses': len(all_syntheses),
            'subcategory_syntheses': 0,
            'main_category_syntheses': 0,
            'staleness_stats': {
                'up_to_date': 0,
                'stale_by_new_items': 0,
                'stale_by_updated_items': 0,
                'stale_by_removed_items': 0,
                'needs_regeneration': 0,
                'missing_dependencies': 0
            },
            'categories_needing_synthesis': {
                'new_subcategories': [],
                'new_main_categories': []
            },
            'stale_syntheses': []
        }
        
        # Categorize syntheses
        for synthesis in all_syntheses:
            if synthesis.sub_category:
                analysis['subcategory_syntheses'] += 1
            else:
                analysis['main_category_syntheses'] += 1
            
            # Analyze staleness for this synthesis
            staleness_info = self._check_synthesis_staleness(synthesis)
            
            if staleness_info['is_stale']:
                analysis['stale_syntheses'].append({
                    'id': synthesis.id,
                    'main_category': synthesis.main_category,
                    'sub_category': synthesis.sub_category,
                    'staleness_reason': staleness_info['reason'],
                    'last_updated': synthesis.last_updated.isoformat() if synthesis.last_updated else None,
                    'needs_regeneration': synthesis.needs_regeneration
                })
                
                # Update counters
                if staleness_info['reason'] == 'new_items':
                    analysis['staleness_stats']['stale_by_new_items'] += 1
                elif staleness_info['reason'] == 'updated_items':
                    analysis['staleness_stats']['stale_by_updated_items'] += 1
                elif staleness_info['reason'] == 'removed_items':
                    analysis['staleness_stats']['stale_by_removed_items'] += 1
                elif staleness_info['reason'] == 'missing_dependencies':
                    analysis['staleness_stats']['missing_dependencies'] += 1
            else:
                analysis['staleness_stats']['up_to_date'] += 1
            
            if synthesis.needs_regeneration:
                analysis['staleness_stats']['needs_regeneration'] += 1
        
        # Find categories that need new synthesis documents
        new_subcategories = self._find_new_subcategories_needing_synthesis()
        new_main_categories = self._find_new_main_categories_needing_synthesis()
        
        analysis['categories_needing_synthesis']['new_subcategories'] = new_subcategories
        analysis['categories_needing_synthesis']['new_main_categories'] = new_main_categories
        
        self.logger.info(f"Synthesis staleness analysis complete: {analysis['staleness_stats']}")
        return analysis
    
    def _check_synthesis_staleness(self, synthesis: SubcategorySynthesis) -> Dict[str, Any]:
        """
        Check if a specific synthesis document is stale.
        Returns staleness information with reason.
        """
        staleness_info = {
            'is_stale': False,
            'reason': None,
            'details': {}
        }
        
        # If explicitly marked as needing regeneration
        if synthesis.needs_regeneration:
            staleness_info['is_stale'] = True
            staleness_info['reason'] = 'needs_regeneration'
            return staleness_info
        
        # If synthesis is marked as stale in database
        if synthesis.is_stale:
            staleness_info['is_stale'] = True
            staleness_info['reason'] = 'marked_stale'
            return staleness_info
        
        # Check dependency changes
        if synthesis.sub_category:
            # Subcategory synthesis - check KB items
            return self._check_subcategory_synthesis_staleness(synthesis)
        else:
            # Main category synthesis - check subcategory syntheses
            return self._check_main_category_synthesis_staleness(synthesis)
    
    def _check_subcategory_synthesis_staleness(self, synthesis: SubcategorySynthesis) -> Dict[str, Any]:
        """Check staleness for subcategory synthesis based on KB items."""
        staleness_info = {
            'is_stale': False,
            'reason': None,
            'details': {}
        }
        
        # Get current KB items for this subcategory
        current_items = KnowledgeBaseItem.query.filter_by(
            main_category=synthesis.main_category,
            sub_category=synthesis.sub_category
        ).all()
        
        current_item_ids = {item.id for item in current_items}
        current_item_count = len(current_items)
        
        # Parse dependency item IDs
        try:
            dependency_ids = set(json.loads(synthesis.dependency_item_ids or '[]'))
        except (json.JSONDecodeError, TypeError):
            dependency_ids = set()
        
        # Check for new items
        new_items = current_item_ids - dependency_ids
        if new_items:
            staleness_info['is_stale'] = True
            staleness_info['reason'] = 'new_items'
            staleness_info['details']['new_item_count'] = len(new_items)
            staleness_info['details']['new_item_ids'] = list(new_items)
            return staleness_info
        
        # Check for removed items
        removed_items = dependency_ids - current_item_ids
        if removed_items:
            staleness_info['is_stale'] = True
            staleness_info['reason'] = 'removed_items'
            staleness_info['details']['removed_item_count'] = len(removed_items)
            staleness_info['details']['removed_item_ids'] = list(removed_items)
            return staleness_info
        
        # Check for updated items (based on last_item_update timestamp)
        if synthesis.last_item_update and current_items:
            latest_item_update = max(
                item.updated_at if hasattr(item, 'updated_at') and item.updated_at 
                else item.created_at if hasattr(item, 'created_at') and item.created_at
                else datetime.min.replace(tzinfo=timezone.utc)
                for item in current_items
            )
            
            if latest_item_update > synthesis.last_item_update:
                staleness_info['is_stale'] = True
                staleness_info['reason'] = 'updated_items'
                staleness_info['details']['latest_item_update'] = latest_item_update.isoformat()
                staleness_info['details']['synthesis_last_update'] = synthesis.last_item_update.isoformat()
                return staleness_info
        
        # Check content hash if available
        if synthesis.content_hash:
            current_hash = self._calculate_content_hash(current_items)
            if current_hash != synthesis.content_hash:
                staleness_info['is_stale'] = True
                staleness_info['reason'] = 'content_changed'
                staleness_info['details']['current_hash'] = current_hash
                staleness_info['details']['stored_hash'] = synthesis.content_hash
                return staleness_info
        
        return staleness_info
    
    def _check_main_category_synthesis_staleness(self, synthesis: SubcategorySynthesis) -> Dict[str, Any]:
        """Check staleness for main category synthesis based on subcategory syntheses."""
        staleness_info = {
            'is_stale': False,
            'reason': None,
            'details': {}
        }
        
        # Get current subcategory syntheses for this main category
        current_sub_syntheses = SubcategorySynthesis.query.filter(
            and_(
                SubcategorySynthesis.main_category == synthesis.main_category,
                SubcategorySynthesis.sub_category.isnot(None)
            )
        ).all()
        
        # Check if any subcategory synthesis is newer than main category synthesis
        if synthesis.last_updated and current_sub_syntheses:
            latest_sub_update = max(
                sub.last_updated for sub in current_sub_syntheses
                if sub.last_updated
            )
            
            if latest_sub_update and latest_sub_update > synthesis.last_updated:
                staleness_info['is_stale'] = True
                staleness_info['reason'] = 'subcategory_updated'
                staleness_info['details']['latest_subcategory_update'] = latest_sub_update.isoformat()
                staleness_info['details']['main_category_last_update'] = synthesis.last_updated.isoformat()
                return staleness_info
        
        # Check for new subcategory syntheses
        try:
            dependency_ids = set(json.loads(synthesis.dependency_item_ids or '[]'))
        except (json.JSONDecodeError, TypeError):
            dependency_ids = set()
        
        current_sub_ids = {sub.id for sub in current_sub_syntheses}
        new_subcategories = current_sub_ids - dependency_ids
        
        if new_subcategories:
            staleness_info['is_stale'] = True
            staleness_info['reason'] = 'new_subcategories'
            staleness_info['details']['new_subcategory_count'] = len(new_subcategories)
            return staleness_info
        
        return staleness_info
    
    def _calculate_content_hash(self, items: List[KnowledgeBaseItem]) -> str:
        """Calculate SHA256 hash of combined content from KB items."""
        if not items:
            return hashlib.sha256(b'').hexdigest()
        
        # Sort items by ID for consistent hashing
        sorted_items = sorted(items, key=lambda x: x.id)
        
        # Combine relevant content fields
        content_parts = []
        for item in sorted_items:
            content_part = f"{item.id}:{item.title}:{item.content or ''}"
            content_parts.append(content_part)
        
        combined_content = "\n".join(content_parts)
        return hashlib.sha256(combined_content.encode('utf-8')).hexdigest()
    
    def _find_new_subcategories_needing_synthesis(self) -> List[Dict[str, Any]]:
        """Find subcategories that have enough items but no synthesis document."""
        min_items = getattr(self.config, 'synthesis_min_items', 2)
        
        # Get subcategories with sufficient items
        subcategories_with_counts = db.session.query(
            KnowledgeBaseItem.main_category,
            KnowledgeBaseItem.sub_category,
            func.count(KnowledgeBaseItem.id).label('item_count')
        ).group_by(
            KnowledgeBaseItem.main_category,
            KnowledgeBaseItem.sub_category
        ).having(
            func.count(KnowledgeBaseItem.id) >= min_items
        ).all()
        
        # Check which ones don't have synthesis documents
        new_subcategories = []
        for main_cat, sub_cat, count in subcategories_with_counts:
            existing_synthesis = SubcategorySynthesis.query.filter_by(
                main_category=main_cat,
                sub_category=sub_cat
            ).first()
            
            if not existing_synthesis:
                new_subcategories.append({
                    'main_category': main_cat,
                    'sub_category': sub_cat,
                    'item_count': count
                })
        
        return new_subcategories
    
    def _find_new_main_categories_needing_synthesis(self) -> List[Dict[str, Any]]:
        """Find main categories that have enough subcategory syntheses but no main synthesis."""
        min_syntheses = getattr(self.config, 'synthesis_min_sub_syntheses', 2)
        
        # Get main categories with sufficient subcategory syntheses
        main_categories_with_counts = db.session.query(
            SubcategorySynthesis.main_category,
            func.count(SubcategorySynthesis.id).label('synthesis_count')
        ).filter(
            SubcategorySynthesis.sub_category.isnot(None)
        ).group_by(
            SubcategorySynthesis.main_category
        ).having(
            func.count(SubcategorySynthesis.id) >= min_syntheses
        ).all()
        
        # Check which ones don't have main category synthesis documents
        new_main_categories = []
        for main_cat, count in main_categories_with_counts:
            existing_synthesis = SubcategorySynthesis.query.filter_by(
                main_category=main_cat,
                sub_category=None
            ).first()
            
            if not existing_synthesis:
                new_main_categories.append({
                    'main_category': main_cat,
                    'synthesis_count': count
                })
        
        return new_main_categories
    
    def update_synthesis_dependencies(self, synthesis_id: int, source_items: List[Any]) -> None:
        """
        Update dependency tracking for a synthesis document.
        Call this after generating/updating a synthesis.
        """
        synthesis = SubcategorySynthesis.query.get(synthesis_id)
        if not synthesis:
            self.logger.error(f"Synthesis {synthesis_id} not found")
            return
        
        now = datetime.now(timezone.utc)
        
        if synthesis.sub_category:
            # Subcategory synthesis - track KB items
            item_ids = [item.id for item in source_items if hasattr(item, 'id')]
            dependency_ids_json = json.dumps(item_ids)
            
            # Calculate content hash
            if hasattr(source_items[0], 'content'):  # KB items
                content_hash = self._calculate_content_hash(source_items)
            else:
                content_hash = None
            
            # Find latest item update
            latest_update = None
            if source_items:
                for item in source_items:
                    item_update = getattr(item, 'updated_at', None) or getattr(item, 'created_at', None)
                    if item_update and (not latest_update or item_update > latest_update):
                        latest_update = item_update
        else:
            # Main category synthesis - track subcategory syntheses
            synthesis_ids = [item.id for item in source_items if hasattr(item, 'id')]
            dependency_ids_json = json.dumps(synthesis_ids)
            content_hash = None  # Don't hash synthesis content
            
            # Find latest subcategory synthesis update
            latest_update = None
            if source_items:
                for item in source_items:
                    item_update = getattr(item, 'last_updated', None)
                    if item_update and (not latest_update or item_update > latest_update):
                        latest_update = item_update
        
        # Update the synthesis record
        synthesis.dependency_item_ids = dependency_ids_json
        synthesis.content_hash = content_hash
        synthesis.last_item_update = latest_update
        synthesis.is_stale = False
        synthesis.needs_regeneration = False
        synthesis.last_updated = now
        
        db.session.commit()
        
        self.logger.info(f"Updated dependencies for synthesis {synthesis_id}: {len(json.loads(dependency_ids_json))} dependencies")
    
    def mark_affected_syntheses_stale(self, main_category: str, sub_category: Optional[str] = None) -> int:
        """
        Mark synthesis documents as stale when a KB item is added/updated/removed.
        Returns the number of syntheses marked as stale.
        """
        marked_count = 0
        
        # Mark subcategory synthesis as stale
        if sub_category:
            subcategory_synthesis = SubcategorySynthesis.query.filter_by(
                main_category=main_category,
                sub_category=sub_category
            ).first()
            
            if subcategory_synthesis:
                subcategory_synthesis.is_stale = True
                marked_count += 1
        
        # Mark main category synthesis as stale
        main_category_synthesis = SubcategorySynthesis.query.filter_by(
            main_category=main_category,
            sub_category=None
        ).first()
        
        if main_category_synthesis:
            main_category_synthesis.is_stale = True
            marked_count += 1
        
        if marked_count > 0:
            db.session.commit()
            self.logger.info(f"Marked {marked_count} synthesis documents as stale for {main_category}/{sub_category or 'main'}")
        
        return marked_count
    
    def get_stale_syntheses(self) -> List[Tuple[str, Optional[str]]]:
        """
        Get list of (main_category, sub_category) tuples for stale syntheses.
        Used by PhaseExecutionHelper to determine what needs regeneration.
        """
        stale_syntheses = SubcategorySynthesis.query.filter(
            (SubcategorySynthesis.is_stale == True) |
            (SubcategorySynthesis.needs_regeneration == True)
        ).all()
        
        return [(s.main_category, s.sub_category) for s in stale_syntheses]
    
    def create_synthesis_execution_plan(self, force_regenerate: bool = False) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        """
        Create execution plan for synthesis generation, similar to PhaseExecutionHelper.
        Returns dict with 'needs_generation' and 'up_to_date' lists.
        """
        plan = {
            'needs_generation': [],
            'up_to_date': [],
            'new_subcategories': [],
            'new_main_categories': []
        }
        
        if force_regenerate:
            # If forcing, all existing syntheses need regeneration
            all_syntheses = SubcategorySynthesis.query.all()
            plan['needs_generation'] = [(s.main_category, s.sub_category) for s in all_syntheses]
        else:
            # Only stale syntheses need regeneration
            plan['needs_generation'] = self.get_stale_syntheses()
            
            # Up-to-date syntheses
            up_to_date_syntheses = SubcategorySynthesis.query.filter(
                and_(
                    SubcategorySynthesis.is_stale == False,
                    SubcategorySynthesis.needs_regeneration == False
                )
            ).all()
            plan['up_to_date'] = [(s.main_category, s.sub_category) for s in up_to_date_syntheses]
        
        # Always check for new categories needing synthesis
        plan['new_subcategories'] = [
            (cat['main_category'], cat['sub_category'])
            for cat in self._find_new_subcategories_needing_synthesis()
        ]
        
        plan['new_main_categories'] = [
            (cat['main_category'], None)
            for cat in self._find_new_main_categories_needing_synthesis()
        ]
        
        # Combine new categories with existing stale ones
        all_needing_generation = (
            plan['needs_generation'] +
            plan['new_subcategories'] +
            plan['new_main_categories']
        )
        
        # Remove duplicates while preserving order
        seen = set()
        plan['needs_generation'] = []
        for item in all_needing_generation:
            if item not in seen:
                plan['needs_generation'].append(item)
                seen.add(item)
        
        self.logger.info(
            f"Synthesis execution plan: {len(plan['needs_generation'])} need generation, "
            f"{len(plan['up_to_date'])} up-to-date"
        )
        
        return plan 