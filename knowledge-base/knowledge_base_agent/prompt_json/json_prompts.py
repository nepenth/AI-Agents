"""
JSON-based prompt classes that maintain compatibility with the original prompts.py interface.

This module provides JsonLLMPrompts and JsonReasoningPrompts classes that have
identical method signatures to the original LLMPrompts and ReasoningPrompts classes,
but use JSON-based prompt configurations internally.
"""

from typing import Dict, List, Optional, Any
from .prompt_manager import JsonPromptManager
from .base import ModelType


class JsonLLMPrompts:
    """
    JSON-based implementation of LLMPrompts with identical interface.
    
    This class maintains the same method signatures as the original LLMPrompts
    class but uses JSON prompt configurations internally.
    """
    
    def __init__(self, prompt_manager: Optional[JsonPromptManager] = None):
        """
        Initialize with an optional prompt manager.
        
        Args:
            prompt_manager: Optional JsonPromptManager instance
        """
        self.prompt_manager = prompt_manager or JsonPromptManager()
    
    @staticmethod
    def get_categorization_prompt_standard(context_content: str, formatted_existing_categories: str, is_thread: bool = False) -> str:
        """
        Generate a categorization prompt for standard models.
        
        Args:
            context_content: The content to be categorized
            formatted_existing_categories: Formatted list of existing categories
            is_thread: Whether the content is from a thread
            
        Returns:
            The rendered prompt string
        """
        # This will be implemented once we have the JSON prompt files
        # For now, return a placeholder that maintains the interface
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="categorization_standard",
                parameters={
                    "context_content": context_content,
                    "formatted_existing_categories": formatted_existing_categories,
                    "is_thread": is_thread
                }
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation if JSON prompt not available
            from ..prompts import LLMPrompts
            return LLMPrompts.get_categorization_prompt_standard(
                context_content, formatted_existing_categories, is_thread
            )
    
    @staticmethod
    def get_chat_prompt() -> str:
        """
        Returns the enhanced system prompt for the chat functionality.
        """
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="chat_system",
                parameters={}
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_chat_prompt()
    
    @staticmethod 
    def get_chat_context_preparation_prompt() -> str:
        """
        Returns a prompt for preparing context from knowledge base documents for chat queries.
        """
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="chat_context_preparation",
                parameters={}
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_chat_context_preparation_prompt()

    @staticmethod
    def get_synthesis_aware_chat_prompt() -> str:
        """
        Enhanced chat prompt specifically for handling synthesis documents alongside individual items.
        """
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="synthesis_aware_chat",
                parameters={}
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_synthesis_aware_chat_prompt()

    @staticmethod
    def get_contextual_chat_response_prompt(query_type: str = "general") -> str:
        """
        Returns specialized prompts based on the type of query being asked.
        
        Args:
            query_type: Type of query - "explanation", "implementation", "comparison", "troubleshooting", "architecture", "general"
        """
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="contextual_chat_response",
                parameters={"query_type": query_type}
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_contextual_chat_response_prompt(query_type)
    
    @staticmethod
    def get_short_name_generation_prompt() -> str:
        """
        Returns the system prompt for generating a short name for a category.
        """
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="short_name_generation",
                parameters={}
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_short_name_generation_prompt()
    
    @staticmethod
    def get_kb_item_generation_prompt_standard(context_data: Dict[str, Any]) -> str:
        """
        Generate a knowledge base item generation prompt for standard models.
        
        Args:
            context_data: Dictionary containing context information
            
        Returns:
            The rendered prompt string
        """
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="kb_item_generation_standard",
                parameters=context_data
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_kb_item_generation_prompt_standard(context_data)

    @staticmethod
    def get_readme_introduction_prompt_standard(kb_stats: Dict[str, int], category_list: str) -> str:
        """Generate a README introduction prompt for standard models with synthesis awareness"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="readme_introduction_standard",
                parameters={
                    "kb_stats": kb_stats,
                    "category_list": category_list
                }
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_readme_introduction_prompt_standard(kb_stats, category_list)

    @staticmethod
    def get_readme_category_description_prompt_standard(main_display: str, total_cat_items: int, active_subcats: List[str]) -> str:
        """Generate a README category description prompt for standard models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="readme_category_description_standard",
                parameters={
                    "main_display": main_display,
                    "total_cat_items": total_cat_items,
                    "active_subcats": active_subcats
                }
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_readme_category_description_prompt_standard(main_display, total_cat_items, active_subcats)

    @staticmethod
    def get_synthesis_generation_prompt_standard(main_category: str, sub_category: str, kb_items_content: str, synthesis_mode: str = "comprehensive") -> str:
        """Generate a synthesis prompt for standard models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="synthesis_generation_standard",
                parameters={
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "kb_items_content": kb_items_content,
                    "synthesis_mode": synthesis_mode
                }
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_synthesis_generation_prompt_standard(main_category, sub_category, kb_items_content, synthesis_mode)

    @staticmethod
    def get_synthesis_markdown_generation_prompt_standard(synthesis_json: str, main_category: str, sub_category: str, item_count: int) -> str:
        """Generate markdown content from synthesis JSON for standard models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="synthesis_markdown_generation_standard",
                parameters={
                    "synthesis_json": synthesis_json,
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "item_count": item_count
                }
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_synthesis_markdown_generation_prompt_standard(synthesis_json, main_category, sub_category, item_count)

    @staticmethod
    def get_main_category_synthesis_prompt() -> str:
        """Generate a synthesis prompt for main categories (aggregating subcategory syntheses)"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="main_category_synthesis",
                parameters={}
            )
            return result.rendered_prompt
        except:
            # Fallback to original implementation
            from ..prompts import LLMPrompts
            return LLMPrompts.get_main_category_synthesis_prompt()


class JsonReasoningPrompts:
    """
    JSON-based implementation of ReasoningPrompts with identical interface.
    
    This class maintains the same method signatures as the original ReasoningPrompts
    class but uses JSON prompt configurations internally.
    """
    
    def __init__(self, prompt_manager: Optional[JsonPromptManager] = None):
        """
        Initialize with an optional prompt manager.
        
        Args:
            prompt_manager: Optional JsonPromptManager instance
        """
        self.prompt_manager = prompt_manager or JsonPromptManager()
    
    @staticmethod
    def get_system_message() -> Dict[str, str]:
        """Returns the standard system message for reasoning models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="reasoning_system_message",
                parameters={}
            )
            # Parse the result as a message format
            return {
                "role": "system",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_system_message()
    
    @staticmethod
    def get_categorization_prompt(context_content: str, formatted_existing_categories: str, is_thread: bool = False) -> Dict[str, str]:
        """Generate a categorization prompt for reasoning models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="categorization_reasoning",
                parameters={
                    "context_content": context_content,
                    "formatted_existing_categories": formatted_existing_categories,
                    "is_thread": is_thread
                }
            )
            return {
                "role": "user",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_categorization_prompt(context_content, formatted_existing_categories, is_thread)
    
    @staticmethod
    def get_kb_item_generation_prompt(tweet_text: str, categories: Dict[str, str], media_descriptions: Optional[List[str]] = None) -> Dict[str, str]:
        """Generate a knowledge base item generation prompt for reasoning models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="kb_item_generation_reasoning",
                parameters={
                    "tweet_text": tweet_text,
                    "categories": categories,
                    "media_descriptions": media_descriptions or []
                }
            )
            return {
                "role": "user",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_kb_item_generation_prompt(tweet_text, categories, media_descriptions)
    
    @staticmethod
    def get_readme_generation_prompt(kb_stats: Dict[str, int], category_list: str) -> Dict[str, str]:
        """Generate a README introduction prompt for reasoning models with synthesis awareness"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="readme_generation_reasoning",
                parameters={
                    "kb_stats": kb_stats,
                    "category_list": category_list
                }
            )
            return {
                "role": "user",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_readme_generation_prompt(kb_stats, category_list)

    @staticmethod
    def get_readme_category_description_prompt(main_display: str, total_cat_items: int, active_subcats: List[str]) -> Dict[str, str]:
        """Generate a README category description prompt for reasoning models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="readme_category_description_reasoning",
                parameters={
                    "main_display": main_display,
                    "total_cat_items": total_cat_items,
                    "active_subcats": active_subcats
                }
            )
            return {
                "role": "user",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_readme_category_description_prompt(main_display, total_cat_items, active_subcats)

    @staticmethod
    def get_synthesis_generation_prompt(main_category: str, sub_category: str, kb_items_content: str, synthesis_mode: str = "comprehensive") -> Dict[str, str]:
        """Generate a synthesis prompt for reasoning models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="synthesis_generation_reasoning",
                parameters={
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "kb_items_content": kb_items_content,
                    "synthesis_mode": synthesis_mode
                }
            )
            return {
                "role": "user",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_synthesis_generation_prompt(main_category, sub_category, kb_items_content, synthesis_mode)

    @staticmethod
    def get_synthesis_markdown_generation_prompt(synthesis_json: str, main_category: str, sub_category: str, item_count: int) -> Dict[str, str]:
        """Generate markdown content from synthesis JSON for reasoning models"""
        manager = JsonPromptManager()
        
        try:
            result = manager.execute(
                prompt_id="synthesis_markdown_generation_reasoning",
                parameters={
                    "synthesis_json": synthesis_json,
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "item_count": item_count
                }
            )
            return {
                "role": "user",
                "content": result.rendered_prompt
            }
        except:
            # Fallback to original implementation
            from ..prompts import ReasoningPrompts
            return ReasoningPrompts.get_synthesis_markdown_generation_prompt(synthesis_json, main_category, sub_category, item_count)