"""
Synthesis Generator Module for Knowledge Base Agent

This module handles the generation of synthesized learning documents for subcategories.
It analyzes all knowledge base items within each subcategory to extract patterns,
insights, and consolidated knowledge.
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


class SynthesisGenerator:
    """Handles generation of synthesis documents for subcategories."""
    
    def __init__(self, config: Config, http_client: HTTPClient):
        self.config = config
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
    
    async def generate_all_syntheses(
        self,
        preferences: UserPreferences,
        socketio=None,
        phase_emitter_func=None
    ) -> Tuple[List[SynthesisType], int, int]:
        """
        Generate synthesis documents for all subcategories and main categories.
        Returns a list of generated synthesis objects, total eligible count, and total errors.
        """
        self.logger.info("Starting synthesis generation for all categories.")
        
        # Phase 1: Subcategory Synthesis
        sub_syntheses, sub_eligible, sub_errors = await self._generate_subcategory_syntheses(
            preferences, socketio, phase_emitter_func
        )
        
        # Phase 2: Main Category Synthesis (depends on subcategory syntheses)
        main_syntheses, main_eligible, main_errors = await self._generate_main_category_syntheses(
            preferences, socketio, phase_emitter_func
        )
        
        total_syntheses = sub_syntheses + main_syntheses
        total_eligible = sub_eligible + main_eligible
        total_errors = sub_errors + main_errors
        
        self.logger.info(
            f"Completed synthesis generation. Total eligible: {total_eligible}, "
            f"Success: {len(total_syntheses)}, Errors: {total_errors}"
        )
        
        return total_syntheses, total_eligible, total_errors

    async def _generate_subcategory_syntheses(
        self,
        preferences: UserPreferences,
        socketio=None,
        phase_emitter_func=None
    ) -> Tuple[List[SynthesisType], int, int]:
        """Generate synthesis documents for all subcategories with knowledge base items."""
        self.logger.info("Starting subcategory synthesis generation")

        subcategories_with_counts = self._get_subcategories_with_items(preferences.synthesis_min_items)
        num_eligible_subcategories = len(subcategories_with_counts)
        
        # Emit initial main phase update
        if phase_emitter_func:
            if num_eligible_subcategories > 0:
                phase_emitter_func(
                    "synthesis_generation",
                    "in_progress",
                    f"Processing {num_eligible_subcategories} subcategories for synthesis.",
                    is_sub_step_update=False,
                    processed_count=0,
                    total_count=num_eligible_subcategories,
                    error_count=0
                )
            else:
                phase_emitter_func(
                    "synthesis_generation",
                    "completed",
                    "No subcategories eligible for synthesis.",
                    is_sub_step_update=False,
                    processed_count=0,
                    total_count=0,
                    error_count=0
                )

        if not subcategories_with_counts:
            self.logger.info("No subcategories found with sufficient items for synthesis")
            return [], 0, 0

        self.logger.info(f"Found {num_eligible_subcategories} subcategories eligible for synthesis")
        
        synthesis_results = []
        processed_success_count = 0
        error_count_internal = 0
        
        for i, (main_category, sub_category, item_count) in enumerate(subcategories_with_counts):
            # Consider adding stop_flag check here if it becomes available globally or via preferences
            try:
                self.logger.info(f"Generating synthesis for {main_category}/{sub_category} ({item_count} items)")
                
                if phase_emitter_func:
                    phase_emitter_func(
                        "synthesis_generation", 
                        f"Synthesizing: {main_category}/{sub_category} ({i+1}/{num_eligible_subcategories})",
                        "in_progress", # Keep main phase 'in_progress'
                        is_sub_step_update=True, # Mark as sub-step
                        processed_count=processed_success_count,
                        total_count=num_eligible_subcategories,
                        error_count=error_count_internal
                    )
                
                # Check if synthesis already exists and force regeneration is not set
                if not preferences.force_regenerate_synthesis:
                    existing_synthesis = SubcategorySynthesis.query.filter_by(
                        main_category=main_category,
                        sub_category=sub_category
                    ).first()
                    
                    if existing_synthesis:
                        self.logger.info(f"Synthesis already exists for {main_category}/{sub_category}, skipping")
                        processed_success_count +=1
                        # We need to create a SynthesisType object to return for the main category synthesis
                        synthesis_results.append(SynthesisType(
                            main_category=existing_synthesis.main_category,
                            sub_category=existing_synthesis.sub_category,
                            synthesis_title=existing_synthesis.synthesis_title,
                            synthesis_short_name=existing_synthesis.synthesis_short_name,
                            synthesis_content=existing_synthesis.synthesis_content,
                            raw_json_content=existing_synthesis.raw_json_content,
                            item_count=existing_synthesis.item_count,
                            file_path=existing_synthesis.file_path,
                            created_at=existing_synthesis.created_at,
                            last_updated=existing_synthesis.last_updated,
                        ))
                        continue
                
                # Generate synthesis for this subcategory
                synthesis = await self._create_synthesis_document(
                    main_category=main_category, 
                    sub_category=sub_category, 
                    preferences=preferences,
                    is_main_category=False
                )
                
                if synthesis:
                    synthesis_results.append(synthesis)
                    self.logger.info(f"Successfully generated synthesis for {main_category}/{sub_category}")
                    processed_success_count +=1
                else: # _create_synthesis_document returned None
                    error_count_internal += 1
                
            except Exception as e:
                self.logger.error(f"Error generating synthesis for {main_category}/{sub_category}: {e}", exc_info=True)
                error_count_internal += 1
                if phase_emitter_func:
                    phase_emitter_func(
                        "synthesis_generation",
                        f"Error for {main_category}/{sub_category}: {str(e)[:100]}...",
                        "in_progress", # Keep main phase 'in_progress'
                        is_sub_step_update=True,
                        processed_count=processed_success_count,
                        total_count=num_eligible_subcategories,
                        error_count=error_count_internal
                    )
                continue
        
        self.logger.info(f"Subcategory synthesis generation finished. Success: {processed_success_count}, Eligible: {num_eligible_subcategories}, Errors: {error_count_internal}")
        return synthesis_results, num_eligible_subcategories, error_count_internal

    async def _generate_main_category_syntheses(
        self,
        preferences: UserPreferences,
        socketio=None,
        phase_emitter_func=None
    ) -> Tuple[List[SynthesisType], int, int]:
        """Generate synthesis documents for main categories from subcategory syntheses."""
        self.logger.info("Starting main category synthesis generation")
        
        main_categories_with_counts = self._get_main_categories_with_syntheses(
            min_syntheses=self.config.synthesis_min_sub_syntheses
        )
        num_eligible_main_categories = len(main_categories_with_counts)

        if phase_emitter_func:
            # This is a sub-phase of the main "synthesis_generation"
            phase_emitter_func(
                "synthesis_generation",
                "in_progress",
                f"Processing {num_eligible_main_categories} main categories for synthesis.",
                is_sub_step_update=True
            )

        if not main_categories_with_counts:
            self.logger.info("No main categories found with sufficient sub-syntheses.")
            return [], 0, 0

        self.logger.info(f"Found {num_eligible_main_categories} main categories for synthesis.")
        
        synthesis_results = []
        processed_success_count = 0
        error_count_internal = 0

        for i, (main_category, synth_count) in enumerate(main_categories_with_counts):
            try:
                self.logger.info(f"Generating synthesis for main category '{main_category}' ({synth_count} sub-syntheses)")
                
                if phase_emitter_func:
                    phase_emitter_func(
                        "synthesis_generation",
                        f"Synthesizing Main Cat: {main_category} ({i+1}/{num_eligible_main_categories})",
                        "in_progress",
                        is_sub_step_update=True,
                        processed_count=processed_success_count,
                        total_count=num_eligible_main_categories,
                        error_count=error_count_internal
                    )

                if not preferences.force_regenerate_synthesis:
                    existing_synthesis = SubcategorySynthesis.query.filter_by(
                        main_category=main_category,
                        sub_category=None
                    ).first()
                    if existing_synthesis:
                        self.logger.info(f"Main category synthesis already exists for '{main_category}', skipping.")
                        processed_success_count +=1
                        synthesis_results.append(SynthesisType(
                            main_category=existing_synthesis.main_category,
                            sub_category=existing_synthesis.sub_category,
                            synthesis_title=existing_synthesis.synthesis_title,
                            synthesis_short_name=existing_synthesis.synthesis_short_name,
                            synthesis_content=existing_synthesis.synthesis_content,
                            raw_json_content=existing_synthesis.raw_json_content,
                            item_count=existing_synthesis.item_count,
                            file_path=existing_synthesis.file_path,
                            created_at=existing_synthesis.created_at,
                            last_updated=existing_synthesis.last_updated,
                        ))
                        continue
                
                synthesis = await self._create_synthesis_document(
                    main_category=main_category,
                    sub_category=None,
                    preferences=preferences,
                    is_main_category=True
                )
                
                if synthesis:
                    synthesis_results.append(synthesis)
                    processed_success_count += 1
                else:
                    error_count_internal += 1

            except Exception as e:
                self.logger.error(f"Error generating main category synthesis for '{main_category}': {e}", exc_info=True)
                error_count_internal += 1
                if phase_emitter_func:
                     phase_emitter_func(
                        "synthesis_generation",
                        f"Error for main cat {main_category}: {str(e)[:100]}...",
                        "in_progress",
                        is_sub_step_update=True,
                        processed_count=processed_success_count,
                        total_count=num_eligible_main_categories,
                        error_count=error_count_internal
                    )
                continue

        self.logger.info(f"Main category synthesis generation finished. Success: {processed_success_count}, Eligible: {num_eligible_main_categories}, Errors: {error_count_internal}")
        return synthesis_results, num_eligible_main_categories, error_count_internal

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
                synthesis_content_for_llm, item_count = self._get_main_category_content(main_category, preferences)
                if not synthesis_content_for_llm:
                    return None
            else:
                kb_items = KnowledgeBaseItem.query.filter_by(
                    main_category=main_category,
                    sub_category=sub_category
                ).limit(preferences.synthesis_max_items).all()
                
                if not kb_items:
                    self.logger.warning(f"No knowledge base items found for {main_category}/{sub_category}")
                    return None
                
                synthesis_content_for_llm = self._extract_items_content(kb_items)
                item_count = len(kb_items)

            # Generate synthesis JSON using LLM
            synthesis_json = await self._generate_synthesis_json(
                main_category, 
                target_name, 
                synthesis_content_for_llm, 
                preferences.synthesis_mode,
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
            
            # Write to filesystem and database
            synthesis_obj = await self._write_synthesis_document(
                main_category,
                sub_category, # Can be None for main category
                synthesis_json,
                synthesis_markdown,
                item_count,
                short_name
            )
            
            return synthesis_obj
            
        except Exception as e:
            self.logger.error(f"Error creating synthesis document for {target_name}: {e}", exc_info=True)
            return None

    def _get_main_category_content(self, main_category: str, preferences: UserPreferences) -> Optional[Tuple[str, int]]:
        """Aggregates content from subcategory syntheses for a main category."""
        self.logger.debug(f"Aggregating content for main category: {main_category}")
        
        sub_syntheses = SubcategorySynthesis.query.filter(
            SubcategorySynthesis.main_category == main_category,
            SubcategorySynthesis.sub_category.isnot(None) # Ensure we only get subcats
        ).limit(preferences.synthesis_max_items).all()

        if not sub_syntheses:
            self.logger.warning(f"No subcategory syntheses found for main category: {main_category}")
            return None, 0
        
        content_parts = []
        for synth in sub_syntheses:
            try:
                json_content = json.loads(synth.raw_json_content)
                summary = json_content.get("synthesis_summary", "") or json_content.get("executive_summary", "")

                if summary:
                     content_parts.append(f"## Sub-Category: {synth.sub_category}\n\n**Summary:**\n{summary}\n\n---\n")
                else:
                    # Fallback to a portion of the content if no summary fields are found
                    content_parts.append(f"## Sub-Category: {synth.sub_category}\n\n{synth.synthesis_content[:1000]}...\n\n---\n")

            except (json.JSONDecodeError, KeyError) as e:
                self.logger.error(f"Could not parse or extract content from sub-synthesis for '{main_category}/{synth.sub_category}': {e}")
                # Fallback to using the markdown content directly
                content_parts.append(f"## Sub-Category: {synth.sub_category}\n\n{synth.synthesis_content[:1000]}...\n\n---\n")

        return "\n".join(content_parts), len(sub_syntheses)

    def _extract_items_content(self, kb_items: List[KnowledgeBaseItem]) -> str:
        """Extract text content from knowledge base items, excluding media."""
        
        content_parts = []
        
        for item in kb_items:
            item_content = f"## {item.display_title or item.title}\n\n"
            
            if item.description:
                item_content += f"**Description**: {item.description}\n\n"
            
            if item.content:
                content = item.content
                if len(content) > 3000:
                    content = content[:3000] + "... [content truncated]"
                item_content += content
            
            item_content += "\n\n---\n\n"
            content_parts.append(item_content)
        
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
                model=self.config.synthesis_model or self.config.text_model,
                prompt=full_prompt,
                temperature=0.7,
                max_tokens=self.config.max_synthesis_tokens,
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
        is_main_category: bool = False,
    ) -> Optional[str]:
        """Generate markdown document from synthesis JSON."""
        
        try:
            title = synthesis_json.get("synthesis_title", f"Synthesis for {target_name}")
            summary = synthesis_json.get("synthesis_summary", "No summary provided.")
            key_takeaways = synthesis_json.get("key_takeaways", [])
            
            markdown_parts = []
            
            if is_main_category:
                markdown_parts.append(f"# Learning Synthesis: {main_category}\n\n")
            else:
                markdown_parts.append(f"# Learning Synthesis: {main_category} / {target_name}\n\n")

            markdown_parts.append(f"**Generated at**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
            if is_main_category:
                markdown_parts.append(f"**Based on {item_count} sub-category syntheses.**\n\n")
            else:
                markdown_parts.append(f"**Based on {item_count} knowledge items.**\n\n")
            
            markdown_parts.append("## Executive Summary\n\n")
            markdown_parts.append(f"{summary}\n\n")
            
            if key_takeaways:
                markdown_parts.append("## Key Takeaways\n\n")
                for takeaway in key_takeaways:
                    markdown_parts.append(f"- **{takeaway.get('point', 'Key Point')}**: {takeaway.get('explanation', '')}\n")
                markdown_parts.append("\n")
            
            for key, value in synthesis_json.items():
                if key not in ["synthesis_title", "synthesis_summary", "key_takeaways"]:
                    section_title = key.replace('_', ' ').title()
                    markdown_parts.append(f"## {section_title}\n\n")
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                for sub_key, sub_val in item.items():
                                     markdown_parts.append(f"- **{sub_key.replace('_', ' ').title()}**: {sub_val}\n")
                            else:
                                markdown_parts.append(f"- {item}\n")
                    else:
                        markdown_parts.append(f"{value}\n")
                    markdown_parts.append("\n")

            return "".join(markdown_parts)
            
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
        short_name: Optional[str]
    ) -> Optional[SynthesisType]:
        """Write synthesis document to filesystem and database."""
        
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
            
            # Use kb_synthesis_dir from config
            file_path = self.config.kb_synthesis_dir.joinpath(*[normalize_name_for_filesystem(p) for p in path_parts])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            await async_write_text(file_path, synthesis_markdown)
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
                new_synthesis = SubcategorySynthesis(
                    main_category=main_category,
                    sub_category=sub_category,
                    synthesis_title=synthesis_title,
                    synthesis_short_name=short_name,
                    synthesis_content=synthesis_markdown,
                    raw_json_content=json.dumps(synthesis_json, indent=2),
                    item_count=item_count,
                    file_path=str(file_path),
                    created_at=now,
                    last_updated=now
                )
                db.session.add(new_synthesis)
                db_synthesis = new_synthesis
                self.logger.info(f"Added new synthesis for '{target_name}' to database.")
            
            db.session.commit()
            
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
                last_updated=db_synthesis.last_updated
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