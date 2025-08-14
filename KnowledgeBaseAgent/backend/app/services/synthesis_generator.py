"""
Synthesis document generation service for creating category-based content summaries.
"""

import asyncio
import logging
import json
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from app.services.ai_service import get_ai_service
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.ai.base import GenerationConfig
from app.models.knowledge import KnowledgeItem
from app.models.synthesis import SynthesisDocument
from app.schemas.synthesis import SynthesisDocumentCreate
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SynthesisGenerationResult:
    """Result of synthesis document generation."""
    synthesis_document: SynthesisDocumentCreate
    markdown_content: str
    generation_stats: Dict[str, Any]


class SynthesisGenerator:
    """Service for generating synthesis documents from knowledge base items."""
    
    def __init__(self):
        self.settings = get_settings()
        self.knowledge_base_dir = Path(self.settings.KNOWLEDGE_BASE_DIR)
        self.synthesis_dir = self.knowledge_base_dir / "synthesis"
        self.synthesis_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_synthesis_document(
        self,
        main_category: str,
        sub_category: str,
        knowledge_items: List[KnowledgeItem],
        regenerate: bool = False
    ) -> SynthesisGenerationResult:
        """Generate a synthesis document for a category."""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Check if synthesis already exists and is up to date
            if not regenerate:
                existing_synthesis = await self._check_existing_synthesis(
                    main_category, sub_category, knowledge_items
                )
                if existing_synthesis:
                    logger.info(f"Using existing synthesis for {main_category}/{sub_category}")
                    return existing_synthesis
            
            # Generate synthesis content using AI
            synthesis_data = await self._generate_synthesis_content(
                main_category, sub_category, knowledge_items
            )
            
            # Create markdown content
            markdown_content = await self._create_synthesis_markdown(
                main_category, sub_category, knowledge_items, synthesis_data
            )
            
            # Save markdown file
            markdown_path = await self._save_synthesis_markdown(
                main_category, sub_category, markdown_content
            )
            
            # Calculate content hash for dependency tracking
            content_hash = self._calculate_content_hash(knowledge_items)
            
            # Calculate generation stats
            generation_time = asyncio.get_event_loop().time() - start_time
            generation_stats = {
                "generation_duration": generation_time,
                "source_items_count": len(knowledge_items),
                "total_word_count": sum(len(item.enhanced_content.split()) for item in knowledge_items),
                "synthesis_word_count": len(synthesis_data.get("content", "").split())
            }
            
            # Create synthesis document
            synthesis_document = SynthesisDocumentCreate(
                id=str(uuid.uuid4()),
                main_category=main_category,
                sub_category=sub_category,
                title=synthesis_data.get("title", f"{main_category} - {sub_category} Synthesis"),
                content=synthesis_data.get("content", ""),
                executive_summary=synthesis_data.get("executive_summary"),
                item_count=len(knowledge_items),
                word_count=generation_stats["synthesis_word_count"],
                source_item_ids=[item.id for item in knowledge_items],
                content_hash=content_hash,
                generation_model=synthesis_data.get("model_used"),
                generation_parameters=synthesis_data.get("generation_parameters"),
                generation_duration=generation_time,
                coherence_score=synthesis_data.get("coherence_score"),
                completeness_score=synthesis_data.get("completeness_score"),
                markdown_path=str(markdown_path)
            )
            
            logger.info(f"Generated synthesis document for {main_category}/{sub_category} with {len(knowledge_items)} items")
            
            return SynthesisGenerationResult(
                synthesis_document=synthesis_document,
                markdown_content=markdown_content,
                generation_stats=generation_stats
            )
            
        except Exception as e:
            logger.error(f"Failed to generate synthesis for {main_category}/{sub_category}: {e}")
            raise
    
    async def _check_existing_synthesis(
        self,
        main_category: str,
        sub_category: str,
        knowledge_items: List[KnowledgeItem]
    ) -> Optional[SynthesisGenerationResult]:
        """Check if an existing synthesis is still valid."""
        # This would check the database for existing synthesis
        # For now, always regenerate
        return None
    
    async def _generate_synthesis_content(
        self,
        main_category: str,
        sub_category: str,
        knowledge_items: List[KnowledgeItem]
    ) -> Dict[str, Any]:
        """Generate synthesis content using AI."""
        ai_service = get_ai_service()
        
        # Resolve model for synthesis generation
        router = get_model_router()
        backend_name, model_name, params = await router.resolve(ModelPhase.synthesis)
        
        # Prepare content for synthesis
        content_summary = self._prepare_content_for_synthesis(knowledge_items)
        
        # Create synthesis prompt
        prompt = self._create_synthesis_prompt(main_category, sub_category, content_summary)
        
        # Generate synthesis
        config = GenerationConfig(temperature=float(params.get("temperature", 0.5)), max_tokens=params.get("max_tokens", 1200))
        response = await ai_service.generate_text(prompt, model_name, backend_name=backend_name, config=config)
        
        # Parse the AI response
        synthesis_data = self._parse_synthesis_response(response)
        synthesis_data["model_used"] = model_name
        synthesis_data["generation_parameters"] = config.__dict__
        
        return synthesis_data
    
    def _prepare_content_for_synthesis(self, knowledge_items: List[KnowledgeItem]) -> str:
        """Prepare content summary for synthesis generation."""
        content_parts = []
        
        for i, item in enumerate(knowledge_items[:20], 1):  # Limit to 20 items to avoid token limits
            # Create a summary of each knowledge item
            summary_parts = [f"Item {i}: {item.display_title}"]
            
            if item.summary:
                summary_parts.append(f"Summary: {item.summary}")
            
            if item.key_points:
                key_points_text = "; ".join(item.key_points[:3])  # Limit key points
                summary_parts.append(f"Key Points: {key_points_text}")
            
            # Add truncated content
            content_preview = item.enhanced_content[:300] + "..." if len(item.enhanced_content) > 300 else item.enhanced_content
            summary_parts.append(f"Content: {content_preview}")
            
            content_parts.append("\n".join(summary_parts))
        
        if len(knowledge_items) > 20:
            content_parts.append(f"\n[... and {len(knowledge_items) - 20} more items]")
        
        return "\n\n---\n\n".join(content_parts)
    
    def _create_synthesis_prompt(
        self,
        main_category: str,
        sub_category: str,
        content_summary: str
    ) -> str:
        """Create a prompt for synthesis generation."""
        prompt = f"""Create a comprehensive synthesis document for the category "{main_category} > {sub_category}" based on the following knowledge base items.

KNOWLEDGE BASE ITEMS:
{content_summary}

Please create a synthesis document in the following JSON format:
{{
    "title": "Comprehensive title for the synthesis document",
    "executive_summary": "2-3 sentence high-level summary of the entire synthesis",
    "content": "Detailed synthesis content that integrates and analyzes all the source materials",
    "key_themes": ["Theme 1", "Theme 2", "Theme 3"],
    "main_insights": ["Insight 1", "Insight 2", "Insight 3"],
    "recommendations": ["Recommendation 1", "Recommendation 2"],
    "coherence_score": 0.85,
    "completeness_score": 0.90
}}

Requirements for the synthesis:
- Create a cohesive narrative that connects and analyzes the source materials
- Identify common themes, patterns, and relationships across the content
- Provide unique insights that emerge from analyzing the content together
- Structure the content with clear sections and logical flow
- Include specific examples and references from the source materials
- Avoid simply concatenating or summarizing individual items
- Focus on synthesis, analysis, and insight generation
- Provide actionable recommendations where appropriate
- Assess coherence (how well the synthesis flows) and completeness (how well it covers the source material) on a 0.0-1.0 scale

The content should be substantial (500-1000 words) and provide real value beyond the individual source items.

Respond ONLY with valid JSON, no additional text.

JSON Response:"""
        
        return prompt
    
    def _parse_synthesis_response(self, response: str) -> Dict[str, Any]:
        """Parse the AI synthesis response."""
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
            synthesis_data = {
                "title": data.get("title", "Synthesis Document"),
                "executive_summary": data.get("executive_summary"),
                "content": data.get("content", ""),
                "key_themes": data.get("key_themes", []),
                "main_insights": data.get("main_insights", []),
                "recommendations": data.get("recommendations", []),
                "coherence_score": float(data.get("coherence_score", 0.5)),
                "completeness_score": float(data.get("completeness_score", 0.5))
            }
            
            return synthesis_data
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse AI synthesis response: {e}")
            logger.debug(f"Response was: {response}")
            
            # Return fallback synthesis
            return self._create_fallback_synthesis(response)
    
    def _create_fallback_synthesis(self, response: str) -> Dict[str, Any]:
        """Create fallback synthesis when AI parsing fails."""
        # Use the raw response as content if it looks reasonable
        content = response if len(response) > 100 else "Synthesis generation failed. Please try again."
        
        return {
            "title": "Synthesis Document",
            "executive_summary": "This synthesis document was generated with limited AI processing.",
            "content": content,
            "key_themes": [],
            "main_insights": [],
            "recommendations": [],
            "coherence_score": 0.3,
            "completeness_score": 0.3
        }
    
    async def _create_synthesis_markdown(
        self,
        main_category: str,
        sub_category: str,
        knowledge_items: List[KnowledgeItem],
        synthesis_data: Dict[str, Any]
    ) -> str:
        """Create markdown content for the synthesis document."""
        markdown_lines = []
        
        # Title
        markdown_lines.append(f"# {synthesis_data['title']}")
        markdown_lines.append("")
        
        # Metadata
        markdown_lines.append("## Document Information")
        markdown_lines.append("")
        markdown_lines.append(f"- **Category**: {main_category} > {sub_category}")
        markdown_lines.append(f"- **Source Items**: {len(knowledge_items)}")
        markdown_lines.append(f"- **Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        if synthesis_data.get("model_used"):
            markdown_lines.append(f"- **AI Model**: {synthesis_data['model_used']}")
        if synthesis_data.get("coherence_score"):
            markdown_lines.append(f"- **Coherence Score**: {synthesis_data['coherence_score']:.2f}")
        if synthesis_data.get("completeness_score"):
            markdown_lines.append(f"- **Completeness Score**: {synthesis_data['completeness_score']:.2f}")
        markdown_lines.append("")
        
        # Executive Summary
        if synthesis_data.get("executive_summary"):
            markdown_lines.append("## Executive Summary")
            markdown_lines.append("")
            markdown_lines.append(synthesis_data["executive_summary"])
            markdown_lines.append("")
        
        # Key Themes
        if synthesis_data.get("key_themes"):
            markdown_lines.append("## Key Themes")
            markdown_lines.append("")
            for theme in synthesis_data["key_themes"]:
                markdown_lines.append(f"- {theme}")
            markdown_lines.append("")
        
        # Main Content
        markdown_lines.append("## Synthesis")
        markdown_lines.append("")
        markdown_lines.append(synthesis_data["content"])
        markdown_lines.append("")
        
        # Main Insights
        if synthesis_data.get("main_insights"):
            markdown_lines.append("## Key Insights")
            markdown_lines.append("")
            for insight in synthesis_data["main_insights"]:
                markdown_lines.append(f"- {insight}")
            markdown_lines.append("")
        
        # Recommendations
        if synthesis_data.get("recommendations"):
            markdown_lines.append("## Recommendations")
            markdown_lines.append("")
            for recommendation in synthesis_data["recommendations"]:
                markdown_lines.append(f"- {recommendation}")
            markdown_lines.append("")
        
        # Source Items
        markdown_lines.append("## Source Items")
        markdown_lines.append("")
        markdown_lines.append(f"This synthesis is based on {len(knowledge_items)} knowledge base items:")
        markdown_lines.append("")
        
        for i, item in enumerate(knowledge_items, 1):
            markdown_lines.append(f"{i}. **{item.display_title}**")
            if item.summary:
                markdown_lines.append(f"   - {item.summary}")
            if item.markdown_path:
                markdown_lines.append(f"   - [View Details]({item.markdown_path})")
        
        markdown_lines.append("")
        
        return "\n".join(markdown_lines)
    
    async def _save_synthesis_markdown(
        self,
        main_category: str,
        sub_category: str,
        markdown_content: str
    ) -> Path:
        """Save synthesis markdown to file."""
        # Create filename based on category
        safe_main = main_category.replace(" ", "_").replace("/", "_")
        safe_sub = sub_category.replace(" ", "_").replace("/", "_")
        filename = f"{safe_main}_{safe_sub}_synthesis.md"
        file_path = self.synthesis_dir / filename
        
        # Write file asynchronously
        import aiofiles
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(markdown_content)
        
        logger.info(f"Saved synthesis markdown: {file_path}")
        return file_path
    
    def _calculate_content_hash(self, knowledge_items: List[KnowledgeItem]) -> str:
        """Calculate hash of content for dependency tracking."""
        # Create a hash based on the IDs and update times of knowledge items
        content_data = []
        for item in sorted(knowledge_items, key=lambda x: x.id):
            content_data.append(f"{item.id}:{item.updated_at.isoformat()}")
        
        content_string = "|".join(content_data)
        return hashlib.sha256(content_string.encode()).hexdigest()
    
    async def generate_synthesis_for_category(
        self,
        main_category: str,
        sub_category: str,
        knowledge_items: Optional[List[KnowledgeItem]] = None
    ) -> SynthesisGenerationResult:
        """Generate synthesis for a category, optionally with provided items."""
        if knowledge_items is None:
            # This would query the database for knowledge items in the category
            # For now, raise an error
            raise ValueError("Knowledge items must be provided")
        
        if not knowledge_items:
            raise ValueError(f"No knowledge items found for category {main_category}/{sub_category}")
        
        return await self.generate_synthesis_document(
            main_category, sub_category, knowledge_items
        )
    
    async def batch_generate_synthesis(
        self,
        category_items_map: Dict[Tuple[str, str], List[KnowledgeItem]]
    ) -> List[SynthesisGenerationResult]:
        """Generate synthesis documents for multiple categories."""
        results = []
        
        # Process categories sequentially to avoid overwhelming the AI service
        for (main_category, sub_category), knowledge_items in category_items_map.items():
            try:
                result = await self.generate_synthesis_document(
                    main_category, sub_category, knowledge_items
                )
                results.append(result)
                
                # Small delay between generations
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Failed to generate synthesis for {main_category}/{sub_category}: {e}")
                continue
        
        return results
    
    async def update_synthesis_if_stale(
        self,
        synthesis_doc: SynthesisDocument,
        current_knowledge_items: List[KnowledgeItem]
    ) -> Optional[SynthesisGenerationResult]:
        """Update synthesis document if it's stale."""
        current_hash = self._calculate_content_hash(current_knowledge_items)
        
        if synthesis_doc.content_hash == current_hash and not synthesis_doc.is_stale:
            logger.info(f"Synthesis for {synthesis_doc.category_path} is up to date")
            return None
        
        logger.info(f"Updating stale synthesis for {synthesis_doc.category_path}")
        return await self.generate_synthesis_document(
            synthesis_doc.main_category,
            synthesis_doc.sub_category,
            current_knowledge_items,
            regenerate=True
        )


# Global service instance
_synthesis_generator: Optional[SynthesisGenerator] = None


def get_synthesis_generator() -> SynthesisGenerator:
    """Get the global synthesis generator instance."""
    global _synthesis_generator
    if _synthesis_generator is None:
        _synthesis_generator = SynthesisGenerator()
    return _synthesis_generator