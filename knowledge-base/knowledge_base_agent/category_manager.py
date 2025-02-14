import json
import logging
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any
from knowledge_base_agent.exceptions import CategoryError, ConfigurationError, StorageError

@dataclass
class Category:
    name: str
    subcategories: Set[str]
    description: str
    keywords: Set[str]

class CategoryManager:
    """Manages categories for the knowledge base."""
    
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
    
    def __init__(self, categories_file: Path):
        """
        Initialize the CategoryManager.
        
        Args:
            categories_file: Path to the categories JSON file
            
        Raises:
            ConfigurationError: If the categories file is invalid
        """
        self.categories_file = categories_file
        self.categories: Dict[str, List[str]] = {}
        self.load_categories()

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

    def add_category(self, main_category: str, sub_category: Optional[str] = None) -> None:
        """
        Add a new category or subcategory.
        
        Args:
            main_category: The main category name
            sub_category: Optional subcategory name
            
        Raises:
            CategoryError: If the category is invalid
        """
        try:
            if not main_category:
                raise CategoryError("Main category cannot be empty")

            if main_category not in self.categories:
                self.categories[main_category] = []

            if sub_category:
                if sub_category not in self.categories[main_category]:
                    self.categories[main_category].append(sub_category)

            self._save_categories()
            
        except Exception as e:
            raise CategoryError(f"Failed to add category: {e}")

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
        return sorted(self.categories.keys())

    def get_category_info(self, category: str) -> Optional[dict]:
        return self.categories.get(category)

    def add_main_category(self, category: str, description: str) -> None:
        """Add a main category with description"""
        self.categories[category] = {
            'description': description,
            'subcategories': {}
        }
