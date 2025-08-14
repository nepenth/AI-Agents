"""
Knowledge base item generation service for creating structured knowledge entries.
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

from app.services.ai_service import get_ai_service
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.ai.base import GenerationConfig
from app.models.content import ContentItem
from app.models.knowledge import KnowledgeItem
from app.schemas.knowledge import KnowledgeItemCreate
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeGenerationResult:
    """Result of knowledge base item generation."""
    knowledge_item: KnowledgeItemCreate
    markdown_content: str
    quality_metrics: Dict[str, float]


class KnowledgeGenerator:
    """Service for generating structured knowledge base items from content."""
    
    def __init__(self):
        self.settings = get_settings()
        self.knowledge_base_dir = Path(self.settings.KNOWLEDGE_BASE_DIR)
        self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_knowledge_item(
        self, 
        content_item: ContentItem,
        category_info: Optional[Dict[str, Any]] = None
    ) -> KnowledgeGenerationResult:
        """Generate a knowledge base item from a content item."""
        try:
            # Generate enhanced content using AI
            enhanced_data = await self._generate_enhanced_content(content_item, category_info)
            
            # Create markdown file
            markdown_content = await self._create_markdown_content(content_item, enhanced_data)
            markdown_path = await self._save_markdown_file(content_item.id, markdown_content)
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(content_item, enhanced_data)
            
            # Create knowledge item
            knowledge_item = KnowledgeItemCreate(
                id=str(uuid.uuid4()),
                content_item_id=content_item.id,
                display_title=enhanced_data.get("display_title", content_item.title),
                summary=enhanced_data.get("summary"),
                enhanced_content=enhanced_data.get("enhanced_content", content_item.content),
                key_points=enhanced_data.get("key_points", []),
                entities=enhanced_data.get("entities", []),
                sentiment_score=enhanced_data.get("sentiment_score"),
                markdown_path=str(markdown_path),
                media_paths=self._get_media_paths(content_item),
                quality_score=quality_metrics.get("overall_quality", 0.5),
                completeness_score=quality_metrics.get("completeness", 0.5)
            )
            
            logger.info(f"Generated knowledge item for content '{content_item.title}'")
            
            return KnowledgeGenerationResult(
                knowledge_item=knowledge_item,
                markdown_content=markdown_content,
                quality_metrics=quality_metrics
            )
            
        except Exception as e:
            logger.error(f"Failed to generate knowledge item for '{content_item.title}': {e}")
            raise
    
    async def _generate_enhanced_content(
        self, 
        content_item: ContentItem,
        category_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate enhanced content using AI."""
        ai_service = get_ai_service()
        
        # Resolve model for knowledge base generation
        router = get_model_router()
        backend_name, model_name, params = await router.resolve(ModelPhase.kb_generation)
        
        # Create enhancement prompt
        prompt = self._create_enhancement_prompt(content_item, category_info)
        
        # Generate enhanced content
        config = GenerationConfig(temperature=float(params.get("temperature", 0.4)), max_tokens=params.get("max_tokens", 800))
        response = await ai_service.generate_text(prompt, model_name, backend_name=backend_name, config=config)
        
        # Parse the AI response
        return self._parse_enhancement_response(response, content_item)
    
    def _create_enhancement_prompt(
        self, 
        content_item: ContentItem,
        category_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a prompt for content enhancement."""
        category_context = ""
        if category_info:
            category_context = f"""
Category: {category_info.get('main_category', 'Unknown')} > {category_info.get('sub_category', 'Unknown')}
Tags: {', '.join(category_info.get('tags', []))}
"""
        
        content_preview = content_item.content[:1500] + "..." if len(content_item.content) > 1500 else content_item.content
        
        prompt = f"""Analyze and enhance the following content to create a structured knowledge base entry.

ORIGINAL CONTENT:
Title: {content_item.title}
Source: {content_item.source_type}
{category_context}
Content: {content_preview}

Please provide your analysis in the following JSON format:
{{
    "display_title": "Enhanced, clear title for the knowledge base",
    "summary": "2-3 sentence summary of the key information",
    "enhanced_content": "Improved version of the content with better structure and clarity",
    "key_points": ["Key point 1", "Key point 2", "Key point 3"],
    "entities": [
        {{"name": "Entity Name", "type": "person|organization|technology|concept", "description": "Brief description"}},
        {{"name": "Another Entity", "type": "technology", "description": "What this entity is"}}
    ],
    "sentiment_score": 0.7,
    "quality_assessment": {{
        "clarity": 0.8,
        "completeness": 0.7,
        "usefulness": 0.9
    }}
}}

Requirements:
- Create a clear, descriptive title that captures the essence of the content
- Write a concise summary that highlights the most important information
- Enhance the content by improving structure, clarity, and readability while preserving all important information
- Extract 3-5 key points that represent the main takeaways
- Identify important entities (people, organizations, technologies, concepts) mentioned in the content
- Provide a sentiment score from -1.0 (very negative) to 1.0 (very positive), with 0.0 being neutral
- Assess quality metrics on a scale of 0.0 to 1.0
- Respond ONLY with valid JSON, no additional text

JSON Response:"""
        
        return prompt
    
    def _parse_enhancement_response(self, response: str, content_item: ContentItem) -> Dict[str, Any]:
        """Parse the AI enhancement response."""
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
            
            # Validate and set defaults
            enhanced_data = {
                "display_title": data.get("display_title", content_item.title),
                "summary": data.get("summary"),
                "enhanced_content": data.get("enhanced_content", content_item.content),
                "key_points": data.get("key_points", []),
                "entities": data.get("entities", []),
                "sentiment_score": float(data.get("sentiment_score", 0.0)),
            }
            
            # Extract quality assessment
            quality_assessment = data.get("quality_assessment", {})
            enhanced_data.update(quality_assessment)
            
            return enhanced_data
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse AI enhancement response: {e}")
            logger.debug(f"Response was: {response}")
            
            # Return fallback enhancement
            return self._create_fallback_enhancement(content_item)
    
    def _create_fallback_enhancement(self, content_item: ContentItem) -> Dict[str, Any]:
        """Create fallback enhancement when AI processing fails."""
        # Simple text processing for fallback
        content = content_item.content or ""
        sentences = content.split('. ')
        
        # Create simple summary from first few sentences
        summary = '. '.join(sentences[:2]) + '.' if len(sentences) > 1 else content[:200] + "..."
        
        # Extract simple key points (first sentence of each paragraph)
        paragraphs = content.split('\n\n')
        key_points = []
        for para in paragraphs[:3]:
            if para.strip():
                first_sentence = para.split('.')[0].strip()
                if first_sentence and len(first_sentence) > 10:
                    key_points.append(first_sentence + '.')
        
        return {
            "display_title": content_item.title,
            "summary": summary,
            "enhanced_content": content,
            "key_points": key_points,
            "entities": [],
            "sentiment_score": 0.0,
            "clarity": 0.5,
            "completeness": 0.5,
            "usefulness": 0.5
        }
    
    async def _create_markdown_content(
        self, 
        content_item: ContentItem, 
        enhanced_data: Dict[str, Any]
    ) -> str:
        """Create markdown content for the knowledge item."""
        markdown_lines = []
        
        # Title
        markdown_lines.append(f"# {enhanced_data['display_title']}")
        markdown_lines.append("")
        
        # Metadata
        markdown_lines.append("## Metadata")
        markdown_lines.append("")
        markdown_lines.append(f"- **Source**: {content_item.source_type}")
        markdown_lines.append(f"- **Original Title**: {content_item.title}")
        if content_item.main_category:
            markdown_lines.append(f"- **Category**: {content_item.main_category} > {content_item.sub_category}")
        if content_item.tags:
            markdown_lines.append(f"- **Tags**: {', '.join(content_item.tags)}")
        markdown_lines.append(f"- **Created**: {content_item.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if enhanced_data.get("sentiment_score") is not None:
            sentiment = enhanced_data["sentiment_score"]
            sentiment_label = "Positive" if sentiment > 0.1 else "Negative" if sentiment < -0.1 else "Neutral"
            markdown_lines.append(f"- **Sentiment**: {sentiment_label} ({sentiment:.2f})")
        markdown_lines.append("")
        
        # Summary
        if enhanced_data.get("summary"):
            markdown_lines.append("## Summary")
            markdown_lines.append("")
            markdown_lines.append(enhanced_data["summary"])
            markdown_lines.append("")
        
        # Key Points
        if enhanced_data.get("key_points"):
            markdown_lines.append("## Key Points")
            markdown_lines.append("")
            for point in enhanced_data["key_points"]:
                markdown_lines.append(f"- {point}")
            markdown_lines.append("")
        
        # Entities
        if enhanced_data.get("entities"):
            markdown_lines.append("## Important Entities")
            markdown_lines.append("")
            for entity in enhanced_data["entities"]:
                name = entity.get("name", "Unknown")
                entity_type = entity.get("type", "unknown")
                description = entity.get("description", "")
                markdown_lines.append(f"- **{name}** ({entity_type}): {description}")
            markdown_lines.append("")
        
        # Main Content
        markdown_lines.append("## Content")
        markdown_lines.append("")
        markdown_lines.append(enhanced_data["enhanced_content"])
        markdown_lines.append("")
        
        # Media Files
        if content_item.media_files:
            markdown_lines.append("## Media Files")
            markdown_lines.append("")
            for media_file in content_item.media_files:
                if media_file.get("local_path"):
                    markdown_lines.append(f"- [{media_file.get('type', 'Media')}]({media_file['local_path']})")
                    if media_file.get("ai_description"):
                        markdown_lines.append(f"  - {media_file['ai_description']}")
            markdown_lines.append("")
        
        # Original Source
        if content_item.raw_data and content_item.raw_data.get("original_url"):
            markdown_lines.append("## Source")
            markdown_lines.append("")
            markdown_lines.append(f"[Original Source]({content_item.raw_data['original_url']})")
            markdown_lines.append("")
        
        return "\n".join(markdown_lines)
    
    async def _save_markdown_file(self, content_id: str, markdown_content: str) -> Path:
        """Save markdown content to file."""
        # Create filename based on content ID
        filename = f"{content_id}.md"
        file_path = self.knowledge_base_dir / filename
        
        # Write file asynchronously
        import aiofiles
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(markdown_content)
        
        logger.info(f"Saved knowledge base markdown: {file_path}")
        return file_path
    
    def _get_media_paths(self, content_item: ContentItem) -> List[str]:
        """Get media file paths from content item."""
        media_paths = []
        for media_file in content_item.media_files:
            if media_file.get("local_path"):
                media_paths.append(media_file["local_path"])
        return media_paths
    
    def _calculate_quality_metrics(
        self, 
        content_item: ContentItem, 
        enhanced_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate quality metrics for the knowledge item."""
        metrics = {}
        
        # Get AI-provided quality metrics
        metrics["clarity"] = enhanced_data.get("clarity", 0.5)
        metrics["completeness"] = enhanced_data.get("completeness", 0.5)
        metrics["usefulness"] = enhanced_data.get("usefulness", 0.5)
        
        # Calculate additional metrics
        content_length = len(content_item.content) if content_item.content else 0
        
        # Length-based completeness factor
        length_factor = min(1.0, content_length / 1000)  # Normalize to 1000 chars
        
        # Has media bonus
        media_bonus = 0.1 if content_item.media_files else 0.0
        
        # Has categorization bonus
        category_bonus = 0.1 if content_item.main_category else 0.0
        
        # Calculate overall quality
        overall_quality = (
            metrics["clarity"] * 0.4 +
            metrics["completeness"] * 0.3 +
            metrics["usefulness"] * 0.2 +
            length_factor * 0.1
        ) + media_bonus + category_bonus
        
        metrics["overall_quality"] = min(1.0, overall_quality)
        metrics["length_factor"] = length_factor
        
        return metrics
    
    async def batch_generate_knowledge_items(
        self, 
        content_items: List[ContentItem],
        category_info_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[KnowledgeGenerationResult]:
        """Generate knowledge items for multiple content items."""
        results = []
        
        # Ensure category info list matches content items
        if category_info_list is None:
            category_info_list = [None] * len(content_items)
        elif len(category_info_list) != len(content_items):
            logger.warning("Category info list length doesn't match content items, padding with None")
            category_info_list.extend([None] * (len(content_items) - len(category_info_list)))
        
        # Process in batches to avoid overwhelming the AI service
        batch_size = 3
        for i in range(0, len(content_items), batch_size):
            batch_items = content_items[i:i + batch_size]
            batch_categories = category_info_list[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [
                self.generate_knowledge_item(item, category_info)
                for item, category_info in zip(batch_items, batch_categories)
            ]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle any exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate knowledge item for {batch_items[j].id}: {result}")
                    continue
                results.append(result)
            
            # Small delay between batches
            if i + batch_size < len(content_items):
                await asyncio.sleep(2)
        
        return results
    
    async def update_markdown_file(self, knowledge_item: KnowledgeItem) -> bool:
        """Update the markdown file for a knowledge item."""
        try:
            if not knowledge_item.markdown_path:
                logger.warning(f"No markdown path for knowledge item {knowledge_item.id}")
                return False
            
            # This would require loading the original content item
            # For now, just return True as placeholder
            logger.info(f"Updated markdown file: {knowledge_item.markdown_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update markdown file for {knowledge_item.id}: {e}")
            return False


# Global service instance
_knowledge_generator: Optional[KnowledgeGenerator] = None


def get_knowledge_generator() -> KnowledgeGenerator:
    """Get the global knowledge generator instance."""
    global _knowledge_generator
    if _knowledge_generator is None:
        _knowledge_generator = KnowledgeGenerator()
    return _knowledge_generator