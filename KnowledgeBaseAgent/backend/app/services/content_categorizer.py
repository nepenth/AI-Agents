"""
Content categorization service using AI for intelligent content classification.
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from app.services.ai_service import get_ai_service
from app.ai.base import GenerationConfig
from app.models.content import ContentItem

logger = logging.getLogger(__name__)


@dataclass
class CategoryResult:
    """Result of content categorization."""
    main_category: str
    sub_category: str
    tags: List[str]
    confidence_score: float
    reasoning: Optional[str] = None


class ContentCategorizer:
    """Service for categorizing content using AI."""
    
    def __init__(self):
        self.predefined_categories = self._load_predefined_categories()
    
    def _load_predefined_categories(self) -> Dict[str, List[str]]:
        """Load predefined category hierarchy."""
        return {
            "Technology": [
                "Artificial Intelligence",
                "Software Development",
                "Web Development",
                "Mobile Development",
                "DevOps",
                "Cybersecurity",
                "Data Science",
                "Cloud Computing",
                "Hardware",
                "Emerging Tech"
            ],
            "Business": [
                "Strategy",
                "Marketing",
                "Finance",
                "Operations",
                "Leadership",
                "Entrepreneurship",
                "Sales",
                "Product Management",
                "Human Resources",
                "Industry Analysis"
            ],
            "Science": [
                "Computer Science",
                "Physics",
                "Biology",
                "Chemistry",
                "Mathematics",
                "Medicine",
                "Psychology",
                "Environmental Science",
                "Research",
                "Innovation"
            ],
            "Education": [
                "Learning",
                "Teaching",
                "Online Courses",
                "Academic Research",
                "Skills Development",
                "Certification",
                "Training",
                "Knowledge Management",
                "Educational Technology",
                "Career Development"
            ],
            "News": [
                "Technology News",
                "Business News",
                "Science News",
                "Industry Updates",
                "Product Launches",
                "Company News",
                "Market Analysis",
                "Trends",
                "Events",
                "Announcements"
            ],
            "Reference": [
                "Documentation",
                "Tutorials",
                "Guides",
                "Best Practices",
                "Tools",
                "Resources",
                "APIs",
                "Specifications",
                "Standards",
                "Examples"
            ],
            "Personal": [
                "Productivity",
                "Career",
                "Learning Goals",
                "Projects",
                "Ideas",
                "Notes",
                "Bookmarks",
                "Inspiration",
                "Planning",
                "Reflection"
            ]
        }
    
    async def categorize_content(self, content_item: ContentItem) -> CategoryResult:
        """Categorize a content item using AI."""
        try:
            # Prepare content for analysis
            analysis_text = self._prepare_content_for_analysis(content_item)
            
            # Generate categorization using AI
            category_result = await self._generate_categorization(analysis_text)
            
            # Validate and refine the result
            validated_result = self._validate_categorization(category_result)
            
            logger.info(f"Categorized content '{content_item.title}' as {validated_result.main_category}/{validated_result.sub_category}")
            
            return validated_result
            
        except Exception as e:
            logger.error(f"Failed to categorize content '{content_item.title}': {e}")
            # Return default categorization
            return CategoryResult(
                main_category="Personal",
                sub_category="Notes",
                tags=["uncategorized"],
                confidence_score=0.1,
                reasoning=f"Categorization failed: {str(e)}"
            )
    
    def _prepare_content_for_analysis(self, content_item: ContentItem) -> str:
        """Prepare content text for AI analysis."""
        # Combine title and content, truncate if too long
        title = content_item.title or ""
        content = content_item.content or ""
        
        # Limit content length for AI processing
        max_content_length = 2000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        analysis_text = f"Title: {title}\n\nContent: {content}"
        
        # Add source context if available
        if content_item.source_type:
            analysis_text = f"Source: {content_item.source_type}\n{analysis_text}"
        
        return analysis_text
    
    async def _generate_categorization(self, content_text: str) -> CategoryResult:
        """Generate categorization using AI."""
        ai_service = get_ai_service()
        
        # Get available text generation models
        models = await ai_service.list_models()
        text_models = [m for m in models if m.get("type") == "text_generation"]
        
        if not text_models:
            raise Exception("No text generation models available")
        
        model_name = text_models[0]["name"]
        
        # Create categorization prompt
        prompt = self._create_categorization_prompt(content_text)
        
        # Generate response
        config = GenerationConfig(temperature=0.3, max_tokens=300)
        response = await ai_service.generate_text(prompt, model_name, config=config)
        
        # Parse the AI response
        return self._parse_categorization_response(response)
    
    def _create_categorization_prompt(self, content_text: str) -> str:
        """Create a prompt for AI categorization."""
        categories_text = self._format_categories_for_prompt()
        
        prompt = f"""Analyze the following content and categorize it according to the provided category hierarchy.

CONTENT TO ANALYZE:
{content_text}

AVAILABLE CATEGORIES:
{categories_text}

Please provide your categorization in the following JSON format:
{{
    "main_category": "Category Name",
    "sub_category": "Subcategory Name", 
    "tags": ["tag1", "tag2", "tag3"],
    "confidence_score": 0.85,
    "reasoning": "Brief explanation of why this categorization was chosen"
}}

Requirements:
- Choose the most appropriate main_category and sub_category from the provided hierarchy
- Generate 3-5 relevant tags that describe the content
- Provide a confidence score between 0.0 and 1.0
- Give a brief reasoning for your choice
- Respond ONLY with valid JSON, no additional text

JSON Response:"""
        
        return prompt
    
    def _format_categories_for_prompt(self) -> str:
        """Format the category hierarchy for the AI prompt."""
        formatted_categories = []
        
        for main_cat, sub_cats in self.predefined_categories.items():
            sub_cats_text = ", ".join(sub_cats)
            formatted_categories.append(f"- {main_cat}: {sub_cats_text}")
        
        return "\n".join(formatted_categories)
    
    def _parse_categorization_response(self, response: str) -> CategoryResult:
        """Parse the AI response into a CategoryResult."""
        try:
            # Clean up the response
            response = response.strip()
            
            # Find JSON in the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_text = response[json_start:json_end]
            
            # Parse JSON
            data = json.loads(json_text)
            
            return CategoryResult(
                main_category=data.get("main_category", "Personal"),
                sub_category=data.get("sub_category", "Notes"),
                tags=data.get("tags", []),
                confidence_score=float(data.get("confidence_score", 0.5)),
                reasoning=data.get("reasoning")
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse AI categorization response: {e}")
            logger.debug(f"Response was: {response}")
            
            # Fallback to simple keyword-based categorization
            return self._fallback_categorization(response)
    
    def _fallback_categorization(self, content_text: str) -> CategoryResult:
        """Fallback categorization using simple keyword matching."""
        content_lower = content_text.lower()
        
        # Simple keyword matching
        tech_keywords = ["ai", "artificial intelligence", "programming", "code", "software", "api", "python", "javascript"]
        business_keywords = ["business", "marketing", "strategy", "finance", "startup", "company"]
        science_keywords = ["research", "study", "science", "data", "analysis", "experiment"]
        
        if any(keyword in content_lower for keyword in tech_keywords):
            return CategoryResult(
                main_category="Technology",
                sub_category="Software Development",
                tags=["technology", "development"],
                confidence_score=0.6,
                reasoning="Keyword-based fallback categorization"
            )
        elif any(keyword in content_lower for keyword in business_keywords):
            return CategoryResult(
                main_category="Business",
                sub_category="Strategy",
                tags=["business", "strategy"],
                confidence_score=0.6,
                reasoning="Keyword-based fallback categorization"
            )
        elif any(keyword in content_lower for keyword in science_keywords):
            return CategoryResult(
                main_category="Science",
                sub_category="Research",
                tags=["science", "research"],
                confidence_score=0.6,
                reasoning="Keyword-based fallback categorization"
            )
        else:
            return CategoryResult(
                main_category="Personal",
                sub_category="Notes",
                tags=["general", "notes"],
                confidence_score=0.4,
                reasoning="Default fallback categorization"
            )
    
    def _validate_categorization(self, result: CategoryResult) -> CategoryResult:
        """Validate and potentially correct the categorization result."""
        # Check if main category exists
        if result.main_category not in self.predefined_categories:
            logger.warning(f"Invalid main category: {result.main_category}, using fallback")
            result.main_category = "Personal"
            result.sub_category = "Notes"
            result.confidence_score *= 0.5
        
        # Check if sub category exists under main category
        elif result.sub_category not in self.predefined_categories[result.main_category]:
            logger.warning(f"Invalid sub category: {result.sub_category} for {result.main_category}")
            # Use first sub category as fallback
            result.sub_category = self.predefined_categories[result.main_category][0]
            result.confidence_score *= 0.8
        
        # Ensure tags is a list
        if not isinstance(result.tags, list):
            result.tags = []
        
        # Limit number of tags
        result.tags = result.tags[:5]
        
        # Ensure confidence score is in valid range
        result.confidence_score = max(0.0, min(1.0, result.confidence_score))
        
        return result
    
    async def batch_categorize(self, content_items: List[ContentItem]) -> List[CategoryResult]:
        """Categorize multiple content items in batch."""
        results = []
        
        # Process in batches to avoid overwhelming the AI service
        batch_size = 5
        for i in range(0, len(content_items), batch_size):
            batch = content_items[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [self.categorize_content(item) for item in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle any exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to categorize item {batch[j].id}: {result}")
                    # Create fallback result
                    result = CategoryResult(
                        main_category="Personal",
                        sub_category="Notes",
                        tags=["error"],
                        confidence_score=0.1,
                        reasoning=f"Batch processing error: {str(result)}"
                    )
                results.append(result)
            
            # Small delay between batches
            if i + batch_size < len(content_items):
                await asyncio.sleep(1)
        
        return results
    
    def get_category_hierarchy(self) -> Dict[str, List[str]]:
        """Get the predefined category hierarchy."""
        return self.predefined_categories.copy()
    
    def get_all_categories(self) -> List[str]:
        """Get all main categories."""
        return list(self.predefined_categories.keys())
    
    def get_subcategories(self, main_category: str) -> List[str]:
        """Get subcategories for a main category."""
        return self.predefined_categories.get(main_category, [])


# Global service instance
_content_categorizer: Optional[ContentCategorizer] = None


def get_content_categorizer() -> ContentCategorizer:
    """Get the global content categorizer instance."""
    global _content_categorizer
    if _content_categorizer is None:
        _content_categorizer = ContentCategorizer()
    return _content_categorizer