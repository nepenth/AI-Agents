import json
import logging
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Set, Optional

@dataclass
class Category:
    name: str
    subcategories: Set[str]
    description: str
    keywords: Set[str]

class CategoryManager:
    def __init__(self, categories_file: Path):
        self.categories_file = categories_file
        self.categories: Dict[str, Category] = {}
        self._lock = asyncio.Lock()
        self._initialize_default_categories()
        self.load_categories()

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
            self.categories[cat_name] = Category(
                name=cat_name,
                subcategories=details["subcategories"],
                description=details["description"],
                keywords={word.lower() for word in details["keywords"]}
            )

    def save_categories(self):
        categories_dict = {
            name: {
                "subcategories": list(cat.subcategories),
                "description": cat.description,
                "keywords": list(cat.keywords)
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

    def load_categories(self):
        if self.categories_file.exists():
            try:
                with self.categories_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.categories = {
                        name: Category(
                            name=name,
                            subcategories=set(details["subcategories"]),
                            description=details["description"],
                            keywords={word.lower() for word in details["keywords"]}
                        )
                        for name, details in data.items()
                    }
                logging.info(f"Loaded {len(self.categories)} categories from file")
            except Exception as e:
                logging.error(f"Error loading categories: {e}")
        else:
            self.save_categories()
            logging.info("Created new categories file with defaults")

    def add_category(self, name: str, description: str, keywords: Set[str]) -> bool:
        normalized_name = self._normalize_name(name)
        if normalized_name in self.categories:
            return False
        self.categories[normalized_name] = Category(
            name=normalized_name,
            subcategories=set(),
            description=description,
            keywords={word.lower() for word in keywords}
        )
        self.save_categories()
        return True

    def add_subcategory(self, category: str, subcategory: str) -> bool:
        if category not in self.categories:
            return False
        normalized_sub = self._normalize_name(subcategory)
        self.categories[category].subcategories.add(normalized_sub)
        self.save_categories()
        return True

    def get_category_suggestions(self, content: str, num_suggestions: int = 3) -> List[tuple]:
        content_words = set(self._normalize_name(content).split('_'))
        suggestions = []
        for cat_name, category in self.categories.items():
            keyword_matches = len(content_words & category.keywords)
            if keyword_matches > 0:
                best_subcategory = None
                best_subscore = 0
                for subcategory in category.subcategories:
                    subscore = len(content_words & set(subcategory.split('_')))
                    if subscore > best_subscore:
                        best_subscore = subscore
                        best_subcategory = subcategory
                score = keyword_matches + (best_subscore * 0.5)
                suggestions.append((cat_name, best_subcategory or "best_practices", score))
        return sorted(suggestions, key=lambda x: x[2], reverse=True)[:num_suggestions]

    def _normalize_name(self, name: str) -> str:
        return name.lower().replace(' ', '_').strip('_')

    def get_all_categories(self) -> List[str]:
        return sorted(self.categories.keys())

    def get_subcategories(self, category: str) -> List[str]:
        if category in self.categories:
            return sorted(self.categories[category].subcategories)
        return []

    def get_category_info(self, category: str) -> Optional[Category]:
        return self.categories.get(category)
