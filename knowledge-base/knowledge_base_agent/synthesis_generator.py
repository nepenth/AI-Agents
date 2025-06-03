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
from .types import SubcategorySynthesis as SubcategorySynthesisType
from .prompts import LLMPrompts, ReasoningPrompts, UserPreferences
from .file_utils import async_write_text
from .naming_utils import normalize_name_for_filesystem


class SynthesisGenerator:
    """Handles generation of synthesis documents for subcategories."""
    
    def __init__(self, config: Config, http_client: HTTPClient):
        self.config = config
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
    
    async def generate_all_subcategory_syntheses(
        self,
        preferences: UserPreferences,
        socketio=None,
        phase_emitter_func=None
    ) -> Tuple[List[SubcategorySynthesisType], int, int]:
        """Generate synthesis documents for all subcategories with knowledge base items.
        Returns a list of generated synthesis objects, the count of eligible subcategories, and errors.
        """
        self.logger.info("Starting subcategory synthesis generation")

        subcategories_with_counts = self._get_subcategories_with_items(preferences.synthesis_min_items)
        num_eligible_subcategories = len(subcategories_with_counts)
        
        # Emit initial main phase update
        if phase_emitter_func:
            if num_eligible_subcategories > 0:
                phase_emitter_func(
                    "synthesis_generation",
                    f"Processing {num_eligible_subcategories} subcategories for synthesis.",
                    "in_progress",
                    is_sub_step_update=False,
                    processed_count=0,
                    total_count=num_eligible_subcategories,
                    error_count=0
                )
            else:
                phase_emitter_func(
                    "synthesis_generation",
                    "No subcategories eligible for synthesis.",
                    "completed", 
                    is_sub_step_update=False,
                    processed_count=0,
                    total_count=0,
                    error_count=0
                )

        if not subcategories_with_counts:
            self.logger.info("No subcategories found with sufficient items for synthesis")
            return [], 0, 0 # MODIFIED: return eligible_count and error_count

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
                        continue
                
                # Generate synthesis for this subcategory
                synthesis = await self._create_synthesis_document(
                    main_category, 
                    sub_category, 
                    preferences
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
        
        # Agent.py will emit the final 'completed' or 'error' status for the main phase
        # This function now just returns the detailed counts.
        
        self.logger.info(f"Synthesis generation sub-process finished. Success: {len(synthesis_results)}, Eligible: {num_eligible_subcategories}, Errors: {error_count_internal}")
        return synthesis_results, num_eligible_subcategories, error_count_internal # MODIFIED: return counts
    
    def _get_subcategories_with_items(self, min_items: int) -> List[Tuple[str, str, int]]:
        """Get all subcategories that have at least min_items knowledge base items."""
        
        # Query to get subcategories with item counts
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
        sub_category: str,
        preferences: UserPreferences
    ) -> Optional[SubcategorySynthesisType]:
        """Create a comprehensive synthesis document for a subcategory."""
        
        try:
            # Get all knowledge base items for this subcategory
            kb_items = KnowledgeBaseItem.query.filter_by(
                main_category=main_category,
                sub_category=sub_category
            ).limit(preferences.synthesis_max_items).all()
            
            if not kb_items:
                self.logger.warning(f"No knowledge base items found for {main_category}/{sub_category}")
                return None
            
            # Extract content from knowledge base items (excluding media)
            kb_items_content = self._extract_items_content(kb_items)
            
            # Generate synthesis JSON using LLM
            synthesis_json = await self._generate_synthesis_json(
                main_category, 
                sub_category, 
                kb_items_content, 
                preferences.synthesis_mode
            )
            
            if not synthesis_json:
                self.logger.error(f"Failed to generate synthesis JSON for {main_category}/{sub_category}")
                return None
            
            # Convert JSON to markdown
            synthesis_markdown = await self._generate_synthesis_markdown(
                synthesis_json, 
                main_category, 
                sub_category, 
                len(kb_items)
            )
            
            if not synthesis_markdown:
                self.logger.error(f"Failed to generate synthesis markdown for {main_category}/{sub_category}")
                return None
            
            # Write to filesystem and database
            synthesis_obj = await self._write_synthesis_document(
                main_category,
                sub_category,
                synthesis_json,
                synthesis_markdown,
                len(kb_items)
            )
            
            return synthesis_obj
            
        except Exception as e:
            self.logger.error(f"Error creating synthesis document for {main_category}/{sub_category}: {e}", exc_info=True)
            return None
    
    def _extract_items_content(self, kb_items: List[KnowledgeBaseItem]) -> str:
        """Extract text content from knowledge base items, excluding media."""
        
        content_parts = []
        
        for item in kb_items:
            item_content = f"## {item.display_title or item.title}\n\n"
            
            # Add description if available
            if item.description:
                item_content += f"**Description**: {item.description}\n\n"
            
            # Add main content (truncated if very long)
            if item.content:
                content = item.content
                # Truncate very long content to keep synthesis manageable
                if len(content) > 3000:
                    content = content[:3000] + "... [content truncated]"
                item_content += content
            
            item_content += "\n\n---\n\n"
            content_parts.append(item_content)
        
        return "\n".join(content_parts)
    
    async def _generate_synthesis_json(
        self,
        main_category: str,
        sub_category: str,
        kb_items_content: str,
        synthesis_mode: str
    ) -> Optional[str]:
        """Generate synthesis JSON using LLM."""
        
        try:
            # Determine the base model for synthesis (defaults to text_model if not set in config)
            base_synthesis_model_name = self.config.synthesis_model 

            model_name_to_use = base_synthesis_model_name
            if self.config.enable_synthesis_thinking: # Use the new boolean flag for synthesis
                if isinstance(self.config.synthesis_thinking_model_name, str) and self.config.synthesis_thinking_model_name:
                    model_name_to_use = self.config.synthesis_thinking_model_name # Use the new string field for synthesis thinking model name
                    self.logger.info(f"Using dedicated synthesis thinking model: {model_name_to_use}")
                else:
                    self.logger.warning(
                        "Config 'enable_synthesis_thinking' is True, but 'synthesis_thinking_model_name' is not set or invalid. "
                        f"Falling back to base synthesis model: {base_synthesis_model_name} for JSON generation."
                    )
            else:
                self.logger.info(f"Using standard synthesis model: {model_name_to_use}")
            
            if not isinstance(model_name_to_use, str) or not model_name_to_use:
                 self.logger.error(f"No valid LLM model name configured for synthesis JSON generation. Final attempted model: '{model_name_to_use}'")
                 return None

            # self.config.text_model_thinking determines API style (chat vs. generate)
            if self.config.text_model_thinking: 
                messages = [
                    ReasoningPrompts.get_system_message(),
                    ReasoningPrompts.get_synthesis_generation_prompt(
                        main_category, sub_category, kb_items_content, synthesis_mode
                    )
                ]
                self.logger.debug(f"Attempting synthesis JSON generation with model {model_name_to_use} via /chat endpoint.")
                response = await self.http_client.ollama_chat(
                    model=model_name_to_use, 
                    messages=messages,
                    timeout=self.config.content_generation_timeout
                )
            else:
                prompt = LLMPrompts.get_synthesis_generation_prompt_standard(
                    main_category, sub_category, kb_items_content, synthesis_mode
                )
                self.logger.debug(f"Attempting synthesis JSON generation with model {model_name_to_use} via /generate endpoint.")
                response = await self.http_client.ollama_generate(
                    model=model_name_to_use, 
                    prompt=prompt,
                    timeout=self.config.content_generation_timeout
                )
            
            if not response:
                self.logger.error(f"Empty response from LLM for synthesis generation")
                return None
            
            # Extract and validate JSON
            response_text = response.strip()
            
            # Try to extract JSON from response
            try:
                # Look for JSON block
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    if json_end > json_start:
                        response_text = response_text[json_start:json_end].strip()
                
                # Validate JSON
                synthesis_data = json.loads(response_text)
                
                # Basic validation
                required_fields = ["synthesis_title", "executive_summary", "core_concepts", "key_insights"]
                for field in required_fields:
                    if field not in synthesis_data:
                        self.logger.error(f"Missing required field '{field}' in synthesis JSON")
                        return None
                
                return response_text
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON in synthesis response: {e}")
                self.logger.debug(f"Response text: {response_text}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error generating synthesis JSON: {e}", exc_info=True)
            return None
    
    async def _generate_synthesis_markdown(
        self,
        synthesis_json: str,
        main_category: str,
        sub_category: str,
        item_count: int
    ) -> Optional[str]:
        """Generate synthesis markdown from JSON."""
        
        try:
            # Determine the base model for synthesis (defaults to text_model if not set in config)
            base_synthesis_model_name = self.config.synthesis_model

            model_name_to_use = base_synthesis_model_name
            if self.config.enable_synthesis_thinking: # Use the new boolean flag for synthesis
                if isinstance(self.config.synthesis_thinking_model_name, str) and self.config.synthesis_thinking_model_name:
                    model_name_to_use = self.config.synthesis_thinking_model_name # Use the new string field for synthesis thinking model name
                    self.logger.info(f"Using dedicated synthesis thinking model for markdown: {model_name_to_use}")
                else:
                    self.logger.warning(
                        "Config 'enable_synthesis_thinking' is True, but 'synthesis_thinking_model_name' is not set or invalid. "
                        f"Falling back to base synthesis model: {base_synthesis_model_name} for markdown generation."
                    )
            else:
                self.logger.info(f"Using standard synthesis model for markdown: {model_name_to_use}")

            if not isinstance(model_name_to_use, str) or not model_name_to_use:
                 self.logger.error(f"No valid LLM model name configured for synthesis markdown generation. Final attempted model: '{model_name_to_use}'")
                 return None

            # self.config.text_model_thinking determines API style (chat vs. generate)
            if self.config.text_model_thinking:
                messages = [
                    ReasoningPrompts.get_system_message(),
                    ReasoningPrompts.get_synthesis_markdown_generation_prompt(
                        synthesis_json, main_category, sub_category, item_count
                    )
                ]
                self.logger.debug(f"Attempting synthesis markdown generation with model {model_name_to_use} via /chat endpoint.")
                response = await self.http_client.ollama_chat(
                    model=model_name_to_use, 
                    messages=messages,
                    timeout=self.config.content_generation_timeout
                )
            else:
                prompt = LLMPrompts.get_synthesis_markdown_generation_prompt_standard(
                    synthesis_json, main_category, sub_category, item_count
                )
                self.logger.debug(f"Attempting synthesis markdown generation with model {model_name_to_use} via /generate endpoint.")
                response = await self.http_client.ollama_generate(
                    model=model_name_to_use, 
                    prompt=prompt,
                    timeout=self.config.content_generation_timeout
                )
            
            if not response:
                self.logger.error("Empty response from LLM for markdown generation")
                return None
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating synthesis markdown: {e}", exc_info=True)
            return None
    
    async def _write_synthesis_document(
        self,
        main_category: str,
        sub_category: str,
        synthesis_json: str,
        synthesis_markdown: str,
        item_count: int
    ) -> Optional[SubcategorySynthesisType]:
        """Write synthesis document to filesystem and database."""
        
        try:
            # Extract title from JSON
            synthesis_data = json.loads(synthesis_json)
            synthesis_title = synthesis_data.get("synthesis_title", f"{sub_category.title()} Synthesis")
            
            # Create filesystem path
            synthesis_dir = (
                self.config.knowledge_base_dir / 
                normalize_name_for_filesystem(main_category) / 
                normalize_name_for_filesystem(sub_category) / 
                "_synthesis"
            )
            
            synthesis_dir.mkdir(parents=True, exist_ok=True)
            
            synthesis_file_path = synthesis_dir / "README.md"
            
            # Write markdown to file
            with open(synthesis_file_path, 'w', encoding='utf-8') as f:
                f.write(synthesis_markdown)
            
            # Get relative path from project root
            relative_file_path = synthesis_file_path.relative_to(self.config.project_root)
            
            # Create or update database entry
            now = datetime.now()
            
            existing_synthesis = SubcategorySynthesis.query.filter_by(
                main_category=main_category,
                sub_category=sub_category
            ).first()
            
            if existing_synthesis:
                # Update existing
                existing_synthesis.synthesis_title = synthesis_title
                existing_synthesis.synthesis_content = synthesis_markdown
                existing_synthesis.raw_json_content = synthesis_json
                existing_synthesis.item_count = item_count
                existing_synthesis.file_path = str(relative_file_path)
                existing_synthesis.last_updated = now
                db_synthesis = existing_synthesis
            else:
                # Create new
                db_synthesis = SubcategorySynthesis(
                    main_category=main_category,
                    sub_category=sub_category,
                    synthesis_title=synthesis_title,
                    synthesis_content=synthesis_markdown,
                    raw_json_content=synthesis_json,
                    item_count=item_count,
                    file_path=str(relative_file_path),
                    created_at=now,
                    last_updated=now
                )
                db.session.add(db_synthesis)
            
            db.session.commit()
            
            # Create dataclass object
            synthesis_obj = SubcategorySynthesisType(
                main_category=main_category,
                sub_category=sub_category,
                synthesis_title=synthesis_title,
                synthesis_content=synthesis_markdown,
                raw_json_content=synthesis_json,
                item_count=item_count,
                file_path=str(relative_file_path),
                created_at=db_synthesis.created_at,
                last_updated=db_synthesis.last_updated
            )
            
            self.logger.info(f"Synthesis document written to {synthesis_file_path}")
            return synthesis_obj
            
        except Exception as e:
            self.logger.error(f"Error writing synthesis document: {e}", exc_info=True)
            db.session.rollback()
            return None


async def generate_subcategory_syntheses(
    config: Config,
    http_client: HTTPClient,
    preferences: UserPreferences,
    socketio=None,
    phase_emitter_func=None
) -> Tuple[List[SubcategorySynthesisType], int, int]:
    """
    Convenience function to generate synthesis documents for all subcategories.
    
    Args:
        config: System configuration
        http_client: HTTP client for LLM calls
        preferences: User preferences for synthesis generation
        socketio: Optional SocketIO instance for real-time updates
        phase_emitter_func: Optional function for emitting phase updates
        
    Returns:
        Tuple containing:
            - List of generated synthesis documents
            - Count of eligible subcategories
            - Count of errors
    """
    
    generator = SynthesisGenerator(config, http_client)
    return await generator.generate_all_subcategory_syntheses(
        preferences, socketio, phase_emitter_func
    ) 