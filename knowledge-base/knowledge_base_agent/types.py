"""
Type definitions for the knowledge base agent.

This module contains all the core data structures and type definitions used
throughout the knowledge base agent system.
"""

from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime
import json
from pathlib import Path
from dataclasses import dataclass

class TweetMedia(TypedDict):
    """Media information from a tweet."""
    url: str
    type: str  # 'photo', 'video', etc.
    alt_text: Optional[str]

class TweetCategories(TypedDict):
    """Categorization information for a tweet."""
    main_category: str
    sub_category: str
    item_name: str
    model_used: str
    categorized_at: str

class TweetProcessingStatus(TypedDict):
    media_processed: bool
    categories_processed: bool
    kb_item_created: bool
    kb_item_path: Optional[str]
    kb_item_created_at: Optional[str]

class TweetData(TypedDict):
    """Structured tweet data format."""
    id: str
    full_text: str
    media: List[Dict[str, Any]]
    downloaded_media: List[str]
    media_analysis: List[Dict[str, Any]]
    media_processed: bool
    categories: Optional[Dict[str, str]]
    categories_processed: bool
    kb_item_created: bool
    kb_item_path: Optional[str]
    kb_item_created_at: Optional[str]

@dataclass
class CategoryInfo:
    main_category: str
    sub_category: str
    item_name: str
    description: str  # We'll generate this from full_text or image description

@dataclass
class KnowledgeBaseItem:
    display_title: str
    description: str
    markdown_content: str
    raw_json_content: str
    category_info: CategoryInfo
    source_tweet: Dict[str, Any]
    source_media_cache_paths: List[str]
    kb_media_paths_rel_item_dir: str
    kb_item_path_rel_project_root: str
    image_descriptions: List[str]
    created_at: datetime
    last_updated: datetime

@dataclass
class SubcategorySynthesis:
    """Represents a synthesized learning document for a subcategory."""
    main_category: str
    sub_category: str
    synthesis_title: str
    synthesis_content: str
    raw_json_content: str
    item_count: int
    file_path: Optional[str]
    created_at: datetime
    last_updated: datetime

class ProcessingStats:
    """Statistics for content processing."""
    def __init__(self, start_time: datetime):
        self.start_time = start_time
        self.processed_count: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.media_processed: int = 0
        self.categories_processed: int = 0
        self.readme_generated: bool = False
        self.processing_times: List[float] = []

    def add_processing_time(self, time_taken: float) -> None:
        self.processing_times.append(time_taken)

    def get_average_processing_time(self) -> float:
        if not self.processing_times:
            return 0.0
        return sum(self.processing_times) / len(self.processing_times)

    def save_report(self, path: Path) -> None:
        """Save processing statistics to a JSON file."""
        report = {
            "processed_count": self.processed_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "media_processed": self.media_processed,
            "categories_processed": self.categories_processed,
            "readme_generated": self.readme_generated,
            "average_processing_time": self.get_average_processing_time(),
            "timestamp": datetime.now().isoformat()
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(report, f, indent=2) 