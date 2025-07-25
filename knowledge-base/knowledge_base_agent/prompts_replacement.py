"""JSON-based Prompt Management System - Drop-in Replacement

This module provides a drop-in replacement for the original prompts.py module,
using the JSON-based prompt system while maintaining identical interfaces.
"""

import os
from typing import Dict, List, Optional, Any

from .json_prompt_manager import JsonPromptManager


class LLMPrompts:
    """Drop-in replacement for original LLMPrompts class using JSON prompts."""
    
    _manager = None
    
    @classmethod
    def _get_manager(cls):
        """Get or create the JSON prompt manager instance."""
        if cls._manager is None:
            use_json_prompts = os.getenv('USE_JSON_PROMPTS', 'true').lower() == 'true'
            
            if use_json_prompts:
                try:
                    cls._manager = JsonPromptManager()
                except Exception as e:
                    print(f"Warning: Failed to initialize JSON prompt manager: {e}")
                    from . import prompts as original_prompts
                    return original_prompts.LLMPrompts
            else:
                from . import prompts as original_prompts
                return original_prompts.LLMPrompts
        
        return cls._manager
    
    @staticmethod
    def get_categorization_prompt_standard(context_content: str, formatted_existing_categories: str, is_thread: bool = False) -> str:
        """Generate categorization prompt for standard models."""
        manager = LLMPrompts._get_manager()
        
        if not isinstance(manager, JsonPromptManager):
            return manager.get_categorization_prompt_standard(context_content, formatted_existing_categories, is_thread)
        
        try:
            result = manager.render_prompt(
                "categorization_standard",
                {
                    "context_content": context_content,
                    "formatted_existing_categories": formatted_existing_categories,
                    "is_thread": is_thread
                },
                "standard"
            )
            return result.content
        except Exception as e:
            print(f"Warning: JSON prompt failed, falling back to original: {e}")
            from . import prompts as original_prompts
            return original_prompts.LLMPrompts.get_categorization_prompt_standard(context_content, formatted_existing_categories, is_thread)
    
    @staticmethod
    def get_chat_prompt() -> str:
        """Returns the enhanced system prompt for the chat functionality."""
        manager = LLMPrompts._get_manager()
        
        if not isinstance(manager, JsonPromptManager):
            return manager.get_chat_prompt()
        
        try:
            result = manager.render_prompt("chat_standard", {}, "standard")
            return result.content
        except Exception as e:
            print(f"Warning: JSON prompt failed, falling back to original: {e}")
            from . import prompts as original_prompts
            return original_prompts.LLMPrompts.get_chat_prompt()

    @staticmethod
    def get_main_category_synthesis_prompt() -> str:
        """Generate main category synthesis prompt."""
        manager = LLMPrompts._get_manager()
        
        if not isinstance(manager, JsonPromptManager):
            return manager.get_main_category_synthesis_prompt()
        
        try:
            result = manager.render_prompt("main_category_synthesis", {}, "standard")
            return result.content
        except Exception as e:
            print(f"Warning: JSON prompt failed, falling back to original: {e}")
            from . import prompts as original_prompts
            return original_prompts.LLMPrompts.get_main_category_synthesis_prompt()

    @staticmethod
    def get_synthesis_generation_prompt_standard(main_category: str, target_name: str, kb_items_content: str, synthesis_mode: str) -> str:
        """Generate synthesis prompt for standard models."""
        manager = LLMPrompts._get_manager()
        
        if not isinstance(manager, JsonPromptManager):
            return manager.get_synthesis_generation_prompt_standard(main_category, target_name, kb_items_content, synthesis_mode)
        
        try:
            result = manager.render_prompt(
                "synthesis_standard",
                {
                    "main_category": main_category,
                    "target_name": target_name,
                    "kb_items_content": kb_items_content,
                    "synthesis_mode": synthesis_mode
                },
                "standard"
            )
            return result.content
        except Exception as e:
            print(f"Warning: JSON prompt failed, falling back to original: {e}")
            from . import prompts as original_prompts
            return original_prompts.LLMPrompts.get_synthesis_generation_prompt_standard(main_category, target_name, kb_items_content, synthesis_mode)


class ReasoningPrompts:
    """Drop-in replacement for original ReasoningPrompts class using JSON prompts."""
    
    _manager = None
    
    @classmethod
    def _get_manager(cls):
        """Get or create the JSON prompt manager instance."""
        if cls._manager is None:
            use_json_prompts = os.getenv('USE_JSON_PROMPTS', 'true').lower() == 'true'
            
            if use_json_prompts:
                try:
                    cls._manager = JsonPromptManager()
                except Exception as e:
                    print(f"Warning: Failed to initialize JSON prompt manager: {e}")
                    from . import prompts as original_prompts
                    return original_prompts.ReasoningPrompts
            else:
                from . import prompts as original_prompts
                return original_prompts.ReasoningPrompts
        
        return cls._manager
    
    @staticmethod
    def get_categorization_prompt(context_content: str, formatted_existing_categories: str, is_thread: bool = False) -> Dict[str, str]:
        """Generate categorization prompt for reasoning models."""
        manager = ReasoningPrompts._get_manager()
        
        if not isinstance(manager, JsonPromptManager):
            return manager.get_categorization_prompt(context_content, formatted_existing_categories, is_thread)
        
        try:
            result = manager.render_prompt(
                "categorization_reasoning",
                {
                    "context_content": context_content,
                    "formatted_existing_categories": formatted_existing_categories,
                    "is_thread": is_thread
                },
                "reasoning"
            )
            return result.content
        except Exception as e:
            print(f"Warning: JSON prompt failed, falling back to original: {e}")
            from . import prompts as original_prompts
            return original_prompts.ReasoningPrompts.get_categorization_prompt(context_content, formatted_existing_categories, is_thread)
    
    @staticmethod
    def get_system_message() -> Dict[str, str]:
        """Returns the standard system message for reasoning models."""
        manager = ReasoningPrompts._get_manager()
        
        if not isinstance(manager, JsonPromptManager):
            return manager.get_system_message()
        
        try:
            result = manager.render_prompt("system_message", {}, "reasoning")
            return result.content
        except Exception as e:
            print(f"Warning: JSON prompt failed, falling back to original: {e}")
            from . import prompts as original_prompts
            return original_prompts.ReasoningPrompts.get_system_message()


def use_json_prompts(enabled: bool = True):
    """Enable or disable JSON prompt system globally."""
    os.environ['USE_JSON_PROMPTS'] = 'true' if enabled else 'false'
    LLMPrompts._manager = None
    ReasoningPrompts._manager = None


def is_using_json_prompts() -> bool:
    """Check if JSON prompt system is currently enabled."""
    return os.getenv('USE_JSON_PROMPTS', 'true').lower() == 'true'


def get_prompt_system_info() -> Dict[str, Any]:
    """Get information about the current prompt system configuration."""
    using_json = is_using_json_prompts()
    info = {
        "using_json_prompts": using_json,
        "environment_variable": os.getenv('USE_JSON_PROMPTS', 'true'),
        "fallback_available": True
    }
    
    if using_json:
        try:
            manager = JsonPromptManager()
            available_prompts = manager.get_available_prompts()
            info["json_prompts_loaded"] = True
            info["available_prompt_types"] = list(available_prompts.keys())
            info["total_prompts"] = sum(len(prompts) for prompts in available_prompts.values())
        except Exception as e:
            info["json_prompts_loaded"] = False
            info["error"] = str(e)
    
    return info
