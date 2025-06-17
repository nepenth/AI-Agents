"""
Synthesis Generator Module for Knowledge Base Agent

This module handles the generation of synthesized learning documents for subcategories.
It analyzes all knowledge base items within each subcategory to extract patterns,
insights, and consolidated knowledge.

Enhanced with dependency tracking and staleness detection.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .config import Config
from .http_client import HTTPClient
from .models import KnowledgeBaseItem, SubcategorySynthesis, db
from .custom_types import Synthesis as SynthesisType
from .prompts import LLMPrompts, ReasoningPrompts, UserPreferences
from .file_utils import async_write_text
from .naming_utils import (
    normalize_name_for_filesystem, 
    generate_short_name,
)
from .synthesis_tracker import SynthesisDependencyTracker


class SynthesisGenerator:
    """Handles generation of synthesis documents for subcategories with dependency tracking."""
    
    def __init__(self, config: Config, http_client: HTTPClient):
        self.config = config
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
        self.dependency_tracker = SynthesisDependencyTracker(config)
    
    async def generate_all_syntheses(
        self,
        preferences: UserPreferences,
        socketio=None,
        phase_emitter_func=None
    ) -> Tuple[List[SynthesisType], int, int]:
        """
        Generate synthesis documents using dependency tracking for selective regeneration.
        Returns a list of generated synthesis objects, total eligible count, and total errors.
        """
        self.logger.info("Starting synthesis generation with dependency tracking.")
        
        # Analyze current staleness and create execution plan
        if phase_emitter_func:
            phase_emitter_func(
                "synthesis_generation",
                "in_progress", 
                "Analyzing synthesis dependencies and staleness...",
                False, 0, 0, 0
            )
        
        staleness_analysis = self.dependency_tracker.analyze_synthesis_staleness()
        execution_plan = self.dependency_tracker.create_synthesis_execution_plan(
            force_regenerate=preferences.force_regenerate_synthesis
        )
        
        self.logger.info(f"Synthesis staleness analysis: {staleness_analysis['staleness_stats']}")
        self.logger.info(f"Execution plan: {len(execution_plan['needs_generation'])} syntheses need generation")
        
        total_eligible = len(execution_plan['needs_generation'])
        
        if total_eligible == 0:
            self.logger.info("No syntheses need generation - all are up to date")
            if phase_emitter_func:
                phase_emitter_func(
                    "synthesis_generation",
                    "completed",
                    "All synthesis documents are up to date.",
                    False, 0, 0, 0
                )
            return [], 0, 0
        
        if phase_emitter_func:
            phase_emitter_func(
                "synthesis_generation",
                "in_progress",
                f"Generating {total_eligible} synthesis documents...",
                False, 0, total_eligible, 0
            )
        
        # Generate syntheses based on execution plan
        synthesis_results = []
        processed_count = 0
        error_count = 0
        
        # Process subcategories first, then main categories
        subcategory_syntheses = [
            (main_cat, sub_cat) for main_cat, sub_cat in execution_plan['needs_generation']
            if sub_cat is not None
        ]
        main_category_syntheses = [
            (main_cat, sub_cat) for main_cat, sub_cat in execution_plan['needs_generation']
            if sub_cat is None
        ]
        
        # Generate subcategory syntheses
        for i, (main_category, sub_category) in enumerate(subcategory_syntheses):
            try:
                if phase_emitter_func:
                    phase_emitter_func(
                        "synthesis_generation",
                        f"Generating subcategory synthesis: {main_category}/{sub_category}",
                        "in_progress",
                        True, processed_count, total_eligible, error_count
                    )
                
                synthesis = await self._create_synthesis_document(
                    main_category=main_category,
                    sub_category=sub_category,
                    preferences=preferences,
                    is_main_category=False
                )
                
                if synthesis:
                    synthesis_results.append(synthesis)
                    processed_count += 1
                    self.logger.info(f"Successfully generated synthesis for {main_category}/{sub_category}")
                else:
                    error_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error generating synthesis for {main_category}/{sub_category}: {e}", exc_info=True)
                error_count += 1
        
        # Generate main category syntheses
        for i, (main_category, _) in enumerate(main_category_syntheses):
            try:
                if phase_emitter_func:
                    phase_emitter_func(
                        "synthesis_generation",
                        f"Generating main category synthesis: {main_category}",
                        "in_progress",
                        True, processed_count, total_eligible, error_count
                    )
                
                synthesis = await self._create_synthesis_document(
                    main_category=main_category,
                    sub_category=None,
                    preferences=preferences,
                    is_main_category=True
                )
                
                if synthesis:
                    synthesis_results.append(synthesis)
                    processed_count += 1
                    self.logger.info(f"Successfully generated main category synthesis for {main_category}")
                else:
                    error_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error generating main category synthesis for {main_category}: {e}", exc_info=True)
                error_count += 1
        
        self.logger.info(
            f"Synthesis generation complete. Generated: {processed_count}, "
            f"Eligible: {total_eligible}, Errors: {error_count}"
        )
        
        if phase_emitter_func:
            if error_count == 0:
                phase_emitter_func(
                    "synthesis_generation",
                    "completed",
                    f"Successfully generated {processed_count} synthesis documents.",
                    False, processed_count, total_eligible, error_count
                )
            else:
                phase_emitter_func(
                    "synthesis_generation",
                    "completed_with_errors",
                    f"Generated {processed_count} syntheses with {error_count} errors.",
                    False, processed_count, total_eligible, error_count
                )
        
        return synthesis_results, total_eligible, error_count

    def _get_main_categories_with_syntheses(self, min_syntheses: int) -> List[Tuple[str, int]]:
        """Get main categories that have at least min_syntheses subcategory syntheses."""
        
        result = db.session.query(
            SubcategorySynthesis.main_category,
            db.func.count(SubcategorySynthesis.id).label('synthesis_count')
        ).filter(
            SubcategorySynthesis.sub_category.isnot(None)
        ).group_by(
            SubcategorySynthesis.main_category
        ).having(
            db.func.count(SubcategorySynthesis.id) >= min_syntheses
        ).all()
        
        return [(row.main_category, row.synthesis_count) for row in result]

    def _get_subcategories_with_items(self, min_items: int) -> List[Tuple[str, str, int]]:
        """Get all subcategories that have at least min_items knowledge base items."""
        
        result = db.session.query(
            KnowledgeBaseItem.main_category,
            KnowledgeBaseItem.sub_category,
            db.func.count(KnowledgeBaseItem.id).label('item_count')
        ).group_by(
            KnowledgeBaseItem.main_category,
            KnowledgeBaseItem.sub_category
        ).having(
            db.func.count(KnowledgeBaseItem.id) >= min_items
        ).all()
        
        return [(row.main_category, row.sub_category, row.item_count) for row in result]
    
    async def _create_synthesis_document(
        self,
        main_category: str,
        sub_category: Optional[str],
        preferences: UserPreferences,
        is_main_category: bool = False,
    ) -> Optional[SynthesisType]:
        """Create a comprehensive synthesis document for a subcategory or main category."""
        
        target_name = sub_category if sub_category else main_category
        try:
            self.logger.info(f"Creating synthesis document for '{target_name}'")

            # Get content for synthesis
            if is_main_category:
                synthesis_content_for_llm, item_count, source_items = self._get_main_category_content(main_category, preferences)
                if not synthesis_content_for_llm:
                    return None
            else:
                kb_items = KnowledgeBaseItem.query.filter_by(
                    main_category=main_category,
                    sub_category=sub_category
                ).limit(getattr(preferences, 'synthesis_max_items', 50)).all()
                
                if not kb_items:
                    self.logger.warning(f"No knowledge base items found for {main_category}/{sub_category}")
                    return None
                
                synthesis_content_for_llm = self._extract_items_content(kb_items)
                item_count = len(kb_items)
                source_items = kb_items

            # Generate synthesis JSON using LLM
            synthesis_json = await self._generate_synthesis_json(
                main_category, 
                target_name, 
                synthesis_content_for_llm, 
                getattr(preferences, 'synthesis_mode', 'comprehensive'),
                is_main_category
            )
            
            if not synthesis_json:
                self.logger.error(f"Failed to generate synthesis JSON for {target_name}")
                return None
            
            # Generate a short name for UI display
            short_name = await generate_short_name(self.http_client, target_name, is_main_category)

            # Convert JSON to markdown
            synthesis_markdown = await self._generate_synthesis_markdown(
                synthesis_json, 
                main_category, 
                target_name, 
                item_count,
                is_main_category
            )
            
            if not synthesis_markdown:
                self.logger.error(f"Failed to generate synthesis markdown for {target_name}")
                return None
            
            # Write to filesystem and database with dependency tracking
            synthesis_obj = await self._write_synthesis_document(
                main_category,
                sub_category, # Can be None for main category
                synthesis_json,
                synthesis_markdown,
                item_count,
                short_name,
                source_items  # Pass source items for dependency tracking
            )
            
            return synthesis_obj
            
        except Exception as e:
            self.logger.error(f"Error creating synthesis document for {target_name}: {e}", exc_info=True)
            return None

    def _get_main_category_content(self, main_category: str, preferences: UserPreferences) -> Tuple[Optional[str], int, List[Any]]:
        """Aggregates content from subcategory syntheses for a main category."""
        self.logger.debug(f"Aggregating content for main category: {main_category}")
        
        sub_syntheses = SubcategorySynthesis.query.filter(
            SubcategorySynthesis.main_category == main_category,
            SubcategorySynthesis.sub_category.isnot(None) # Ensure we only get subcats
        ).limit(getattr(preferences, 'synthesis_max_items', 50)).all()

        if not sub_syntheses:
            self.logger.warning(f"No subcategory syntheses found for main category: {main_category}")
            return None, 0, []
        
        content_parts = []
        for sub_synthesis in sub_syntheses:
            content_part = f"## Subcategory: {sub_synthesis.sub_category}\n\n"
            content_part += f"**Title:** {sub_synthesis.synthesis_title}\n\n"
            content_part += f"**Content:**\n{sub_synthesis.synthesis_content}\n\n"
            content_part += "---\n\n"
            content_parts.append(content_part)
        
        combined_content = "\n".join(content_parts)
        return combined_content, len(sub_syntheses), sub_syntheses

    def _extract_items_content(self, items: List[KnowledgeBaseItem]) -> str:
        """Extract and combine content from knowledge base items."""
        content_parts = []
        
        for item in items:
            content_part = f"## Item: {item.title or 'Untitled'}\n\n"
            if item.content:
                # Truncate very long content to avoid token limits
                content = item.content[:2000] + ("..." if len(item.content) > 2000 else "")
                content_part += f"**Content:**\n{content}\n\n"
            content_part += "---\n\n"
            content_parts.append(content_part)
        
        return "\n".join(content_parts)
    
    async def _generate_synthesis_json(
        self,
        main_category: str,
        target_name: str,
        kb_items_content: str,
        synthesis_mode: str,
        is_main_category: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Generate synthesis JSON using LLM."""
        
        try:
            if is_main_category:
                system_prompt = LLMPrompts.get_main_category_synthesis_prompt()
            else:
                system_prompt = LLMPrompts.get_synthesis_generation_prompt_standard(main_category, target_name, kb_items_content, synthesis_mode)

            user_message = (
                f"Please generate a synthesis for the main category '{main_category}'. "
                f"The content is aggregated from its sub-category syntheses.\n\n"
                f"{kb_items_content}"
            ) if is_main_category else (
                f"Please generate a synthesis for the sub-category '{target_name}' "
                f"within the main category '{main_category}'.\n\n"
                f"{kb_items_content}"
            )

            # Combine system prompt and user message for the generate method
            full_prompt = f"{system_prompt}\n\n{user_message}"
            
            response_content = await self.http_client.ollama_generate(
                model=getattr(self.config, 'synthesis_model', None) or self.config.text_model,
                prompt=full_prompt,
                temperature=0.7,
                max_tokens=getattr(self.config, 'max_synthesis_tokens', 4000),
                options={"json_mode": True}
            )
            
            if response_content:
                try:
                    return json.loads(response_content)
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to decode JSON from LLM response for '{target_name}'")
                    return None
            
            self.logger.error(f"LLM request failed or returned empty content for '{target_name}'")
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating synthesis JSON for '{target_name}': {e}", exc_info=True)
            return None

    async def _generate_synthesis_markdown(
        self,
        synthesis_json: Dict[str, Any],
        main_category: str,
        target_name: str,
        item_count: int,
        is_main_category: bool = False
    ) -> Optional[str]:
        """Generate markdown content from synthesis JSON."""
        
        try:
            if is_main_category:
                prompt = LLMPrompts.get_synthesis_markdown_generation_prompt_standard(
                    json.dumps(synthesis_json, indent=2), main_category, "main_category", item_count
                )
            else:
                prompt = LLMPrompts.get_synthesis_markdown_generation_prompt_standard(
                    json.dumps(synthesis_json, indent=2), main_category, target_name, item_count
                )
            
            response_content = await self.http_client.ollama_generate(
                model=getattr(self.config, 'synthesis_model', None) or self.config.text_model,
                prompt=prompt,
                temperature=0.7,
                max_tokens=getattr(self.config, 'max_synthesis_tokens', 4000)
            )
            
            return response_content.strip() if response_content else None
            
        except Exception as e:
            self.logger.error(f"Error generating synthesis markdown for '{target_name}': {e}", exc_info=True)
            return None

    async def _write_synthesis_document(
        self,
        main_category: str,
        sub_category: Optional[str],
        synthesis_json: Dict[str, Any],
        synthesis_markdown: str,
        item_count: int,
        short_name: Optional[str],
        source_items: List[Any]  # KB items or sub-syntheses
    ) -> Optional[SynthesisType]:
        """Write synthesis document to filesystem and database with dependency tracking."""
        
        target_name = sub_category or main_category
        try:
            now = datetime.now(timezone.utc)
            
            if sub_category:
                normalized_sub = normalize_name_for_filesystem(sub_category)
                file_name = f"synthesis_{normalized_sub}.md"
                path_parts = [main_category, sub_category, file_name]
                synthesis_title = synthesis_json.get("synthesis_title", f"Synthesis for {sub_category}")
            else:
                file_name = "synthesis_overview.md"
                path_parts = [main_category, file_name]
                synthesis_title = synthesis_json.get("synthesis_title", f"Synthesis for {main_category}")
            
            # Use knowledge_base_dir from config for synthesis storage
            knowledge_base_dir = Path(self.config.knowledge_base_dir)
            synthesis_dir = knowledge_base_dir / "syntheses"
            file_path = synthesis_dir.joinpath(*[normalize_name_for_filesystem(p) for p in path_parts])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            await async_write_text(synthesis_markdown, file_path)
            self.logger.info(f"Synthesis markdown saved to {file_path}")
            
            query = SubcategorySynthesis.query.filter_by(main_category=main_category)
            if sub_category:
                query = query.filter_by(sub_category=sub_category)
            else:
                query = query.filter(SubcategorySynthesis.sub_category.is_(None))
            
            existing_synthesis = query.first()
            
            if existing_synthesis:
                existing_synthesis.synthesis_title = synthesis_title
                existing_synthesis.synthesis_short_name = short_name
                existing_synthesis.synthesis_content = synthesis_markdown
                raw_json_content = json.dumps(synthesis_json, indent=2)
                existing_synthesis.raw_json_content = raw_json_content
                existing_synthesis.item_count = item_count
                existing_synthesis.file_path = str(file_path)
                existing_synthesis.last_updated = now
                db_synthesis = existing_synthesis
                self.logger.info(f"Updated synthesis for '{target_name}' in database.")
            else:
                new_synthesis = SubcategorySynthesis()
                new_synthesis.main_category = main_category
                new_synthesis.sub_category = sub_category
                new_synthesis.synthesis_title = synthesis_title
                new_synthesis.synthesis_short_name = short_name
                new_synthesis.synthesis_content = synthesis_markdown
                new_synthesis.raw_json_content = json.dumps(synthesis_json, indent=2)
                new_synthesis.item_count = item_count
                new_synthesis.file_path = str(file_path)
                new_synthesis.created_at = now
                new_synthesis.last_updated = now
                db.session.add(new_synthesis)
                db_synthesis = new_synthesis
                self.logger.info(f"Added new synthesis for '{target_name}' to database.")
            
            db.session.commit()
            
            # Update dependency tracking
            self.dependency_tracker.update_synthesis_dependencies(db_synthesis.id, source_items)
            
            return SynthesisType(
                main_category=main_category,
                sub_category=sub_category,
                synthesis_title=synthesis_title,
                synthesis_short_name=short_name,
                synthesis_content=synthesis_markdown,
                raw_json_content=db_synthesis.raw_json_content,
                item_count=item_count,
                file_path=str(file_path),
                created_at=db_synthesis.created_at,
                last_updated=db_synthesis.last_updated,
                content_hash=getattr(db_synthesis, 'content_hash', None),
                is_stale=getattr(db_synthesis, 'is_stale', False),
                last_item_update=getattr(db_synthesis, 'last_item_update', None),
                needs_regeneration=getattr(db_synthesis, 'needs_regeneration', False),
                dependency_item_ids=getattr(db_synthesis, 'dependency_item_ids', None)
            )
            
        except Exception as e:
            self.logger.error(f"Error writing synthesis document for '{target_name}': {e}", exc_info=True)
            db.session.rollback()
            return None

async def generate_syntheses(
    config: Config,
    http_client: HTTPClient,
    preferences: UserPreferences,
    socketio=None,
    phase_emitter_func=None
) -> Tuple[List[SynthesisType], int, int]:
    """
    Top-level function to generate all synthesis documents.
    """
    generator = SynthesisGenerator(config, http_client)
    return await generator.generate_all_syntheses(
        preferences, 
        socketio, 
        phase_emitter_func
    ) 