"""
Category Management Module

This module handles the organization and management of knowledge base categories.
It maintains the category hierarchy and ensures consistent category naming and
structure across the knowledge base.

Categories are organized in a two-level hierarchy:
- Top-level categories (e.g., "Programming", "DevOps")
- Subcategories (e.g., "Python", "Docker")

The category structure is stored in a JSON file with the format:
{
    "programming": {
        "python": ["description", "items_count"],
        "javascript": ["description", "items_count"]
    },
    "devops": {
        "docker": ["description", "items_count"],
        "kubernetes": ["description", "items_count"]
    }
}
"""

import json
import logging
import asyncio
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any, Tuple
from knowledge_base_agent.exceptions import CategoryError, ConfigurationError, StorageError
from knowledge_base_agent.file_utils import async_json_load, async_json_dump
from knowledge_base_agent.path_utils import PathNormalizer, DirectoryManager
from knowledge_base_agent.types import CategoryInfo
from knowledge_base_agent.config import Config
from knowledge_base_agent.http_client import HTTPClient
from datetime import datetime

@dataclass
class Category:
    name: str
    subcategories: Set[str]
    description: str
    keywords: Set[str]

class CategoryManager:
    """
    Manages knowledge base categories and their organization.
    
    Handles category creation, validation, and maintenance of the
    category hierarchy. Ensures consistent category naming and structure.
    
    Attributes:
        config: Configuration instance containing category settings
    """
    
    DEFAULT_CATEGORIES = {
        "software_engineering": [
            "design_patterns",
            "code_quality",
            "testing",
            "debugging",
            "performance_optimization",
            "security",
            "documentation",
            "code_review",
            "refactoring",
            "best_practices"
        ],
        "system_design": [
            "architecture_patterns",
            "distributed_systems",
            "scalability",
            "reliability",
            "microservices",
            "api_design",
            "data_storage",
            "caching",
            "load_balancing",
            "message_queues"
        ],
        "devops": [
            "ci_cd",
            "infrastructure_as_code",
            "containerization",
            "orchestration",
            "monitoring",
            "logging",
            "security",
            "automation",
            "cloud_platforms",
            "site_reliability"
        ],
        "cloud_computing": [
            "aws",
            "azure",
            "gcp",
            "serverless",
            "containers",
            "kubernetes",
            "cloud_native",
            "cost_optimization",
            "security",
            "networking"
        ],
        "data_engineering": [
            "data_pipelines",
            "etl_processes",
            "data_warehousing",
            "data_lakes",
            "stream_processing",
            "data_modeling",
            "data_quality",
            "data_governance",
            "big_data",
            "data_integration"
        ],
        "artificial_intelligence": [
            "machine_learning",
            "deep_learning",
            "nlp",
            "computer_vision",
            "mlops",
            "model_deployment",
            "model_monitoring",
            "data_preparation",
            "feature_engineering",
            "model_optimization"
        ],
        "development_tools": [
            "version_control",
            "ide_tools",
            "build_tools",
            "package_managers",
            "debugging_tools",
            "profiling_tools",
            "testing_frameworks",
            "deployment_tools",
            "monitoring_tools",
            "documentation_tools"
        ],
        "programming_languages": [
            "python",
            "javascript",
            "typescript",
            "go",
            "rust",
            "java",
            "kotlin",
            "swift",
            "cpp",
            "shell_scripting"
        ],
        "web_development": [
            "frontend",
            "backend",
            "apis",
            "frameworks",
            "security",
            "performance",
            "accessibility",
            "responsive_design",
            "authentication",
            "state_management"
        ],
        "career_development": [
            "technical_leadership",
            "mentoring",
            "code_reviews",
            "architecture_decisions",
            "team_collaboration",
            "project_management",
            "communication",
            "learning_resources",
            "industry_trends",
            "best_practices"
        ]
    }
    
    def __init__(self, config: Config, http_client: Optional['HTTPClient'] = None):
        self.config = config
        self.http_client = http_client or config.http_client  # Use provided client or from config
        self.categories_file = Path(config.categories_file)
        self.knowledge_base_dir = Path(config.knowledge_base_dir)
        self._initialized = False
        
        # Ensure knowledge base directory exists
        self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Load categories synchronously in __init__
        self._load_categories_sync()

    def _load_categories_sync(self) -> None:
        """Synchronous version of load_categories for __init__"""
        try:
            if not self.categories_file.exists():
                logging.info("Categories file not found. Creating with default categories.")
                self.categories = self.DEFAULT_CATEGORIES.copy()
                self._save_categories()
                return

            with self.categories_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                raise CategoryError("Categories must be a dictionary")
                
            for main_cat, sub_cats in data.items():
                if not isinstance(sub_cats, list):
                    raise CategoryError(f"Subcategories for {main_cat} must be a list")
                    
            self.categories = data
            
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in categories file: {e}")
        except Exception as e:
            raise StorageError(f"Failed to load categories: {e}")

    async def initialize(self) -> None:
        """Initialize the category manager."""
        if not self._initialized:
            await self.load_categories()  # Await the coroutine
            self._initialized = True

    def load_categories(self) -> None:
        """
        Load categories from the JSON file or create with defaults if it doesn't exist.
        
        Raises:
            StorageError: If reading/writing the categories file fails
            CategoryError: If the categories format is invalid
        """
        try:
            if not self.categories_file.exists():
                logging.info("Categories file not found. Creating with default categories.")
                self.categories = self.DEFAULT_CATEGORIES.copy()
                self._save_categories()
                return

            with self.categories_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                raise CategoryError("Categories must be a dictionary")
                
            for main_cat, sub_cats in data.items():
                if not isinstance(sub_cats, list):
                    raise CategoryError(f"Subcategories for {main_cat} must be a list")
                    
            self.categories = data
            
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in categories file: {e}")
        except Exception as e:
            raise StorageError(f"Failed to load categories: {e}")

    def _save_categories(self) -> None:
        """
        Save categories to the JSON file.
        
        Raises:
            StorageError: If writing the categories file fails
        """
        try:
            self.categories_file.parent.mkdir(parents=True, exist_ok=True)
            with self.categories_file.open('w', encoding='utf-8') as f:
                json.dump(self.categories, f, indent=2)
        except Exception as e:
            raise StorageError(f"Failed to save categories: {e}")

    async def add_category(self, category_info: CategoryInfo) -> None:
        """
        Add a new category or subcategory to the knowledge base.
        
        Args:
            category_info: CategoryInfo object containing category details
            
        Raises:
            CategoryError: If category addition fails
        """
        try:
            norm_category = PathNormalizer.normalize_name(category_info['category'])
            norm_subcategory = PathNormalizer.normalize_name(category_info['subcategory'])
            
            categories = await self.load_categories()
            if norm_category not in categories:
                categories[norm_category] = {}
            if norm_subcategory not in categories[norm_category]:
                categories[norm_category][norm_subcategory] = []
                
            await self.save_categories(categories)
            
            # Ensure directory structure exists
            kb_path = self.config.knowledge_base_dir / norm_category / norm_subcategory
            await DirectoryManager.ensure_directory(kb_path)
            
        except Exception as e:
            logging.exception(f"Failed to add category: {category_info['category']}/{category_info['subcategory']}")
            raise

    def get_categories(self) -> Dict[str, List[str]]:
        """Return all categories."""
        return self.categories

    def get_subcategories(self, main_category: str) -> List[str]:
        """
        Get subcategories for a main category.
        
        Args:
            main_category: The main category name
            
        Raises:
            CategoryError: If the main category doesn't exist
        """
        if main_category not in self.categories:
            raise CategoryError(f"Main category '{main_category}' does not exist")
        return self.categories[main_category]

    def validate_categories(self, main_category: str, sub_category: str) -> None:
        """
        Validate that a category combination exists.
        
        Args:
            main_category: The main category name
            sub_category: The subcategory name
            
        Raises:
            CategoryError: If the category combination is invalid
        """
        if main_category not in self.categories:
            raise CategoryError(f"Invalid main category: {main_category}")
        if sub_category not in self.categories[main_category]:
            raise CategoryError(f"Invalid sub-category '{sub_category}' for main category '{main_category}'")

    def get_all_main_categories(self) -> Set[str]:
        """Return all main categories."""
        return set(self.categories.keys())

    def get_all_sub_categories(self) -> Set[str]:
        """Return all subcategories across all main categories."""
        return {sub_cat for sub_cats in self.categories.values() for sub_cat in sub_cats}

    def _initialize_default_categories(self):
        default_structure = {
            "software_engineering": {
                "subcategories": {
                    "design_patterns", "code_quality", "best_practices",
                    "algorithms", "documentation", "code_review"
                },
                "description": "Core software engineering principles and practices",
                "keywords": {
                    "clean code", "patterns", "solid principles", "engineering",
                    "software design", "development practices"
                }
            },
            "system_design": {
                "subcategories": {
                    "architecture", "scalability", "distributed_systems",
                    "system_patterns", "integration", "apis"
                },
                "description": "System architecture and design principles",
                "keywords": {
                    "architecture", "systems", "design", "scale", "distributed",
                    "integration patterns"
                }
            },
            "cloud_computing": {
                "subcategories": {
                    "aws", "azure", "gcp", "cloud_native", "serverless",
                    "containers", "best_practices"
                },
                "description": "Cloud platforms and services",
                "keywords": {
                    "cloud", "aws", "azure", "serverless", "containers", "kubernetes"
                }
            },
            "data_engineering": {
                "subcategories": {
                    "data_pipelines", "etl", "data_modeling", "data_quality",
                    "data_integration", "data_governance", "best_practices"
                },
                "description": "Data engineering and processing",
                "keywords": {
                    "data", "pipelines", "etl", "modeling", "integration", "processing"
                }
            },
        }
        for cat_name, details in default_structure.items():
            self.categories[cat_name] = {
                'description': details["description"],
                'subcategories': {sub: {} for sub in details["subcategories"]},
                'keywords': {word.lower() for word in details["keywords"]}
            }

    def save_categories(self):
        categories_dict = {
            name: {
                "subcategories": list(cat['subcategories'].keys()),
                "description": cat['description'],
                "keywords": list(cat['keywords'])
            }
            for name, cat in self.categories.items()
        }
        try:
            self.categories_file.parent.mkdir(parents=True, exist_ok=True)
            with self.categories_file.open('w', encoding='utf-8') as f:
                json.dump(categories_dict, f, indent=4)
            logging.info(f"Saved {len(self.categories)} categories to {self.categories_file}")
        except Exception as e:
            logging.error(f"Error saving categories: {e}")
            raise

    def _validate_category_structure(self, category: dict) -> bool:
        """Validate category structure and data"""
        try:
            if not category['name'] or not isinstance(category['name'], str):
                return False
            if not isinstance(category['subcategories'], dict):
                return False
            if not isinstance(category['keywords'], set):
                return False
            if not category['description'] or not isinstance(category['description'], str):
                return False
            return True
        except Exception as e:
            logging.error(f"Category validation error: {e}")
            return False

    def add_subcategory(self, main_category: str, subcategory: str) -> bool:
        if main_category not in self.categories:
            return False
        normalized_sub = self._normalize_name(subcategory)
        if normalized_sub not in self.categories[main_category]['subcategories']:
            return False
        self.categories[main_category]['subcategories'][normalized_sub] = {}
        self.save_categories()
        return True

    def _extract_keywords(self, content: str) -> List[str]:
        """
        Extract keywords from the content.
        This implementation lowercases the text, splits it into words,
        and removes common stopwords. Adjust as needed.
        """
        import re
        # Find all word tokens
        words = re.findall(r'\b\w+\b', content.lower())
        # Define a simple list of common stopwords
        stopwords = set([
            'the', 'and', 'a', 'an', 'of', 'in', 'to', 'is', 'it', 'that', 'this', 'for',
            'on', 'with', 'as', 'by', 'at', 'from', 'or', 'but'
        ])
        # Filter out stopwords
        keywords = [word for word in words if word not in stopwords]
        return keywords

    def get_category_suggestions(self, content: str) -> List[Dict[str, Any]]:
        """Get category suggestions based on content keywords."""
        content_words = set(self._extract_keywords(content))
        suggestions = []
        
        for category in self.categories:
            # If category is a simple string, convert it to a dict.
            if isinstance(category, str):
                category = {
                    'main_category': category,
                    'sub_category': category,
                    'keywords': category.split('_')  # e.g. "system_design" -> ["system", "design"]
                }
                logging.debug(f"Converted simple category string to dict: {category}")
            # If category is provided as a list, try converting it to a dict.
            elif isinstance(category, list):
                if len(category) >= 3:
                    category = {
                        'main_category': category[0],
                        'sub_category': category[1],
                        'keywords': category[2]
                    }
                    logging.debug(f"Converted category list to dict: {category}")
                else:
                    logging.warning(f"Skipping invalid category list: {category}")
                    continue
            
            # Ensure category is a dict.
            if not isinstance(category, dict):
                logging.warning(f"Skipping category with invalid format: {category}")
                continue
                
            # Ensure that keywords exist and cast them to a set for intersection.
            keywords = category.get('keywords', [])
            if not isinstance(keywords, list):
                logging.warning(f"Keywords for category {category} are not a list. Skipping...")
                continue
            
            keyword_matches = len(content_words & set(keywords))
            if keyword_matches > 0:
                suggestion = {
                    'main_category': category.get('main_category', ''),
                    'sub_category': category.get('sub_category', ''),
                    'score': keyword_matches,
                    'matching_keywords': list(content_words & set(keywords))
                }
                suggestions.append(suggestion)
        
        # Sort by score descending
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        return suggestions

    def _normalize_name(self, name: str) -> str:
        return name.lower().replace(' ', '_').strip('_')

    def get_all_categories(self) -> List[str]:
        """Get all available categories."""
        return list(self.categories.keys())

    def get_category_info(self, category: str) -> Optional[dict]:
        return self.categories.get(category)

    def add_main_category(self, category: str, description: str) -> None:
        """Add a main category with description"""
        self.categories[category] = {
            'description': description,
            'subcategories': {}
        }

    async def load_categories(self) -> dict:
        """Load categories asynchronously."""
        try:
            return await async_json_load(self.categories_file)
        except FileNotFoundError:
            return {"categories": []}

    async def save_categories(self, categories: dict) -> None:
        """Save categories asynchronously."""
        await async_json_dump(categories, self.categories_file)

    async def get_category_path(self, category_info: CategoryInfo) -> str:
        """
        Get the filesystem path for a category.
        
        Args:
            category_info: CategoryInfo object containing category details
            
        Returns:
            str: Normalized filesystem path for the category
            
        Raises:
            CategoryError: If path generation fails
        """
        # Implementation details...

    async def validate_category(self, category_info: CategoryInfo) -> bool:
        """
        Validate category information.
        
        Args:
            category_info: Category information to validate
            
        Returns:
            True if category is valid, False otherwise
            
        Notes:
            - Categories must be unique
            - Names must conform to file system rules
            - Maximum depth of 2 levels (category/subcategory)
        """
        pass  # Implementation details...

    async def update_indexes(self) -> None:
        """Update category indexes and handle new categories."""
        try:
            # Load current categories
            current_categories = self.get_all_categories()
            
            # Scan knowledge base directory for new categories
            kb_categories = set()
            kb_subcategories = {}
            
            for main_cat in self.config.knowledge_base_dir.iterdir():
                if not main_cat.is_dir() or main_cat.name.startswith('.'):
                    continue
                    
                main_cat_name = self._normalize_name(main_cat.name)
                kb_categories.add(main_cat_name)
                kb_subcategories[main_cat_name] = set()
                
                # Scan subcategories
                for sub_cat in main_cat.iterdir():
                    if not sub_cat.is_dir() or sub_cat.name.startswith('.'):
                        continue
                    sub_cat_name = self._normalize_name(sub_cat.name)
                    kb_subcategories[main_cat_name].add(sub_cat_name)
            
            # Update categories with new findings
            for main_cat in kb_categories:
                if main_cat not in self.categories:
                    self.categories[main_cat] = {
                        'subcategories': {},
                        'description': f"Auto-generated category for {main_cat}",
                        'keywords': {main_cat}
                    }
                
                # Update subcategories
                if main_cat in kb_subcategories:
                    for sub_cat in kb_subcategories[main_cat]:
                        if sub_cat not in self.categories[main_cat]['subcategories']:
                            self.categories[main_cat]['subcategories'][sub_cat] = {}
            
            # Save updated categories
            await self.save_categories()
            logging.info("Category indexes updated successfully")
            
        except Exception as e:
            logging.error(f"Failed to update indexes: {e}")
            raise CategoryError(f"Failed to update indexes: {e}")

    def category_exists(self, main_cat: str, sub_cat: str) -> bool:
        """Check if a category/subcategory combination exists."""
        main_cat = main_cat.lower().replace(' ', '_')
        sub_cat = sub_cat.lower().replace(' ', '_')
        
        # Check if main category exists
        if main_cat not in self.categories:
            return False
            
        # Check if subcategory exists under main category
        return sub_cat in self.categories[main_cat]

    async def classify_content(self, text: str, tweet_id: str) -> Tuple[str, str]:
        """Classify content into main and sub categories."""
        try:
            prompt = f"""Given this content:
{text}

Either classify it into one of these existing categories:
{json.dumps(self.categories, indent=2)}

OR, if none of the existing categories fit well, suggest a new category and subcategory.
The new category should be specific but generalizable to similar content.

Return as a JSON object:
{{
    "category": "category_name",
    "subcategory": "subcategory_name",
    "is_new": true/false,
    "reason": "Brief explanation if suggesting new category"
}}"""

            # Get classification from model
            response = await self.http_client.ollama_generate(
                model=self.config.text_model,
                prompt=prompt,
                temperature=0.1
            )

            # Extract JSON from response using regex
            json_match = re.search(r'\{[^{]*"category":[^}]*"subcategory":[^}]*"is_new":[^}]*\}', response)
            if not json_match:
                logging.error(f"No valid JSON found in response: {response[:200]}...")
                raise CategoryError(f"Invalid response format from model")

            try:
                result = json.loads(json_match.group(0))
                main_cat = result.get('category', '').strip().lower().replace(' ', '_')
                sub_cat = result.get('subcategory', '').strip().lower().replace(' ', '_')
                is_new = result.get('is_new', False)

                if not main_cat or not sub_cat:
                    raise ValueError("Missing category or subcategory")

                if is_new or not self.category_exists(main_cat, sub_cat):
                    logging.info(f"New category suggested: {main_cat}/{sub_cat} - Reason: {result.get('reason')}")
                    # Add new category to our structure
                    if main_cat not in self.categories:
                        self.categories[main_cat] = []
                    if sub_cat not in self.categories[main_cat]:
                        self.categories[main_cat].append(sub_cat)
                        # Save updated categories
                        self._save_categories()
                        logging.info(f"Added new category combination: {main_cat}/{sub_cat}")
                
                return main_cat, sub_cat
                
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON for tweet {tweet_id}: {e}")
                raise CategoryError(f"Failed to parse model response: {e}")
                
        except Exception as e:
            logging.error(f"Failed to classify content for tweet {tweet_id}: {e}")
            raise CategoryError(f"Classification failed: {e}")

    async def generate_item_name(self, text: str, main_category: str, sub_category: str, tweet_id: str) -> str:
        """Generate a descriptive name for the content."""
        try:
            prompt = f"""Given this content and its categories, generate a short descriptive name.
Content: {text}
Main Category: {main_category}
Sub Category: {sub_category}

The name should be:
- Brief but descriptive
- Lowercase with underscores
- No special characters
- Max 50 characters

Respond with just the name, no explanation."""

            name = await self.http_client.ollama_generate(
                model=self.config.text_model,
                prompt=prompt
            )
            
            # Clean up the name
            name = name.strip().lower()
            name = re.sub(r'[^a-z0-9_]', '_', name)
            name = re.sub(r'_+', '_', name)
            name = name[:50].strip('_')
            
            return name
            
        except Exception as e:
            logging.error(f"Failed to generate name for tweet {tweet_id}: {e}")
            raise CategoryError(f"Name generation failed: {e}")

    async def process_categories(self, tweet_id: str, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and assign categories to a tweet."""
        try:
            # Skip if already categorized
            if tweet_data.get('categories_processed', False):
                logging.info(f"Categories already processed for tweet {tweet_id}, skipping...")
                return tweet_data

            # Generate categories
            tweet_text = tweet_data.get('full_text', '')
            image_descriptions = tweet_data.get('image_descriptions', [])
            combined_text = f"{tweet_text}\n\nImage Descriptions:\n" + "\n".join(image_descriptions)

            # Get categories and item name
            main_cat, sub_cat = await self.classify_content(
                text=combined_text,
                tweet_id=tweet_id
            )

            # Generate item name
            item_name = await self.generate_item_name(
                text=combined_text,
                main_category=main_cat,
                sub_category=sub_cat,
                tweet_id=tweet_id
            )
            
            # Save categories
            tweet_data['categories'] = {
                'main_category': main_cat,
                'sub_category': sub_cat,
                'item_name': item_name,
                'model_used': self.config.text_model,
                'categorized_at': datetime.now().isoformat()
            }
            tweet_data['categories_processed'] = True

            return tweet_data

        except Exception as e:
            logging.error(f"Failed to process categories for tweet {tweet_id}: {str(e)}")
            raise CategoryError(f"Failed to process categories: {str(e)}")

    def sanitize_category_name(self, name: str) -> str:
        """Sanitize category names for URLs/paths"""
        return (
            name.strip()
               .lower()
               .replace(' ', '_')
               .replace('(', '')
               .replace(')', '')
               .replace(',', '')
               .replace("'", "")
               .replace('&', 'and')
        )
