 am"""
Database Validation and Repair Module

This module provides validation and repair functionality for Knowledge Base items
to ensure data consistency between filesystem and database.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import json
from datetime import datetime, timezone

from knowledge_base_agent.models import db, KnowledgeBaseItem as DBKnowledgeBaseItem
from knowledge_base_agent.config import Config


class DatabaseValidator:
    """Validates and repairs Knowledge Base items in the database."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def validate_kb_items(self) -> Dict[str, Any]:
        """
        Validate all KB items in the database for completeness and consistency.
        
        Returns:
            Dict containing validation results and statistics
        """
        self.logger.info("Starting KB items validation...")
        
        validation_results = {
            'total_items': 0,
            'valid_items': 0,
            'invalid_items': 0,
            'missing_content': 0,
            'missing_files': 0,
            'empty_content': 0,
            'invalid_categories': 0,
            'issues': []
        }
        
        try:
            # Get all KB items from database
            all_items = DBKnowledgeBaseItem.query.all()
            validation_results['total_items'] = len(all_items)
            
            for item in all_items:
                issues = self._validate_single_item(item)
                
                if issues:
                    validation_results['invalid_items'] += 1
                    validation_results['issues'].extend(issues)
                    
                    # Count specific issue types
                    for issue in issues:
                        if 'missing content' in issue['description'].lower():
                            validation_results['missing_content'] += 1
                        elif 'missing file' in issue['description'].lower():
                            validation_results['missing_files'] += 1
                        elif 'empty content' in issue['description'].lower():
                            validation_results['empty_content'] += 1
                        elif 'invalid categor' in issue['description'].lower():
                            validation_results['invalid_categories'] += 1
                else:
                    validation_results['valid_items'] += 1
            
            self.logger.info(f"Validation complete: {validation_results['valid_items']}/{validation_results['total_items']} items valid")
            
        except Exception as e:
            self.logger.error(f"Error during validation: {e}", exc_info=True)
            validation_results['error'] = str(e)
        
        return validation_results
    
    def _validate_single_item(self, item: DBKnowledgeBaseItem) -> List[Dict[str, Any]]:
        """
        Validate a single KB item for common issues.
        
        Returns:
            List of issues found with the item
        """
        issues = []
        
        # Check for missing or empty content
        if not item.content or not item.content.strip():
            issues.append({
                'item_id': item.id,
                'tweet_id': item.tweet_id,
                'type': 'missing_content',
                'description': f'Item {item.id} has missing or empty content field',
                'severity': 'high'
            })
        
        # Check for missing title
        if not item.title or not item.title.strip():
            issues.append({
                'item_id': item.id,
                'tweet_id': item.tweet_id,
                'type': 'missing_title',
                'description': f'Item {item.id} has missing or empty title',
                'severity': 'medium'
            })
        
        # Check for invalid categories
        if not item.main_category or item.main_category.strip() == 'Uncategorized':
            issues.append({
                'item_id': item.id,
                'tweet_id': item.tweet_id,
                'type': 'invalid_category',
                'description': f'Item {item.id} has invalid main category: {item.main_category}',
                'severity': 'medium'
            })
        
        # Check for missing file path
        if item.file_path:
            file_path = self.config.resolve_path_from_project_root(item.file_path)
            if not file_path.exists():
                issues.append({
                    'item_id': item.id,
                    'tweet_id': item.tweet_id,
                    'type': 'missing_file',
                    'description': f'Item {item.id} references missing file: {item.file_path}',
                    'severity': 'low'
                })
        
        # Check for missing raw JSON content (indicates incomplete processing)
        if not item.raw_json_content:
            issues.append({
                'item_id': item.id,
                'tweet_id': item.tweet_id,
                'type': 'missing_raw_json',
                'description': f'Item {item.id} missing raw JSON content (incomplete processing)',
                'severity': 'medium'
            })
        
        return issues
    
    def repair_kb_items(self, tweet_data_map: Dict[str, Dict[str, Any]], 
                       force_repair: bool = False) -> Dict[str, Any]:
        """
        Repair KB items in the database using data from tweet_data_map.
        
        Args:
            tweet_data_map: Map of tweet_id to tweet data with processed content
            force_repair: If True, repair all items regardless of validation status
            
        Returns:
            Dict containing repair results and statistics
        """
        self.logger.info("Starting KB items repair...")
        
        repair_results = {
            'total_processed': 0,
            'repaired_items': 0,
            'failed_repairs': 0,
            'skipped_items': 0,
            'repairs': []
        }
        
        try:
            for tweet_id, tweet_data in tweet_data_map.items():
                repair_results['total_processed'] += 1
                
                try:
                    # Get existing DB item
                    db_item = DBKnowledgeBaseItem.query.filter_by(tweet_id=tweet_id).first()
                    
                    if not db_item:
                        self.logger.debug(f"No DB item found for tweet {tweet_id}, skipping repair")
                        repair_results['skipped_items'] += 1
                        continue
                    
                    # Check if repair is needed
                    needs_repair = force_repair or self._item_needs_repair(db_item, tweet_data)
                    
                    if not needs_repair:
                        repair_results['skipped_items'] += 1
                        continue
                    
                    # Perform repair
                    repair_info = self._repair_single_item(db_item, tweet_data)
                    
                    if repair_info['success']:
                        repair_results['repaired_items'] += 1
                        repair_results['repairs'].append(repair_info)
                        self.logger.info(f"Successfully repaired item for tweet {tweet_id}")
                    else:
                        repair_results['failed_repairs'] += 1
                        self.logger.warning(f"Failed to repair item for tweet {tweet_id}: {repair_info.get('error')}")
                
                except Exception as e:
                    repair_results['failed_repairs'] += 1
                    self.logger.error(f"Error repairing item for tweet {tweet_id}: {e}", exc_info=True)
            
            # Commit all changes
            db.session.commit()
            
            self.logger.info(f"Repair complete: {repair_results['repaired_items']} items repaired, "
                           f"{repair_results['failed_repairs']} failures")
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error during repair operation: {e}", exc_info=True)
            repair_results['error'] = str(e)
        
        return repair_results
    
    def _item_needs_repair(self, db_item: DBKnowledgeBaseItem, tweet_data: Dict[str, Any]) -> bool:
        """
        Check if a database item needs repair based on tweet data.
        
        Returns:
            True if the item needs repair, False otherwise
        """
        # Check for missing or empty content
        if not db_item.content or not db_item.content.strip():
            return True
        
        # Check if tweet data has better content
        if tweet_data.get('markdown_content') and not db_item.content:
            return True
        
        # Check for missing raw JSON content
        if not db_item.raw_json_content and tweet_data.get('raw_json_content'):
            return True
        
        # Check for missing display title
        if not db_item.display_title and tweet_data.get('display_title'):
            return True
        
        # Check for missing description
        if not db_item.description and tweet_data.get('description'):
            return True
        
        return False
    
    def _repair_single_item(self, db_item: DBKnowledgeBaseItem, 
                           tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repair a single database item using tweet data.
        
        Returns:
            Dict containing repair results
        """
        repair_info = {
            'item_id': db_item.id,
            'tweet_id': db_item.tweet_id,
            'success': False,
            'changes': []
        }
        
        try:
            # Repair content field
            if not db_item.content or not db_item.content.strip():
                new_content = (tweet_data.get('markdown_content') or 
                             tweet_data.get('full_text_cleaned') or 
                             tweet_data.get('full_text', ''))
                
                if new_content and new_content.strip():
                    db_item.content = new_content
                    repair_info['changes'].append('content')
            
            # Repair display title
            if not db_item.display_title and tweet_data.get('display_title'):
                db_item.display_title = tweet_data['display_title']
                repair_info['changes'].append('display_title')
            
            # Repair description
            if not db_item.description and tweet_data.get('description'):
                db_item.description = tweet_data['description']
                repair_info['changes'].append('description')
            
            # Repair raw JSON content
            if not db_item.raw_json_content and tweet_data.get('raw_json_content'):
                db_item.raw_json_content = tweet_data['raw_json_content']
                repair_info['changes'].append('raw_json_content')
            
            # Repair title if missing
            if not db_item.title or not db_item.title.strip():
                new_title = (tweet_data.get('item_name_suggestion') or 
                           tweet_data.get('display_title') or 
                           f'Tweet {db_item.tweet_id}')
                db_item.title = new_title
                repair_info['changes'].append('title')
            
            # Repair categories if they're default/invalid
            if (db_item.main_category == 'Uncategorized' and 
                tweet_data.get('main_category') and 
                tweet_data['main_category'] != 'Uncategorized'):
                db_item.main_category = tweet_data['main_category']
                repair_info['changes'].append('main_category')
            
            if (db_item.sub_category == 'General' and 
                tweet_data.get('sub_category') and 
                tweet_data['sub_category'] != 'General'):
                db_item.sub_category = tweet_data['sub_category']
                repair_info['changes'].append('sub_category')
            
            # Update last_updated timestamp
            if repair_info['changes']:
                db_item.last_updated = datetime.now(timezone.utc)
                repair_info['changes'].append('last_updated')
            
            repair_info['success'] = True
            
        except Exception as e:
            repair_info['error'] = str(e)
            self.logger.error(f"Error repairing item {db_item.id}: {e}", exc_info=True)
        
        return repair_info
    
    def get_items_needing_repair(self) -> List[int]:
        """
        Get a list of item IDs that need repair.
        
        Returns:
            List of item IDs that have validation issues
        """
        validation_results = self.validate_kb_items()
        return [issue['item_id'] for issue in validation_results.get('issues', [])]