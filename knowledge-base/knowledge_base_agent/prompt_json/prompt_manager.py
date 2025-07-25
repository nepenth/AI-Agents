"""
JSON Prompt Manager for runtime operations.

This module provides the JsonPromptManager class that handles loading, caching,
and managing JSON prompt configurations at runtime.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from .base import PromptLoader, PromptExecutor, ValidationResult, PromptResult, ModelType
from .json_prompt import JsonPrompt
from .schema_validator import JsonSchemaValidator


class JsonPromptManager(PromptLoader, PromptExecutor):
    """
    Manages JSON prompts with loading, caching, and execution capabilities.
    """
    
    def __init__(self, prompt_directory: Optional[str] = None):
        """
        Initialize the prompt manager.
        
        Args:
            prompt_directory: Directory containing JSON prompt files
        """
        self.prompt_directory = Path(prompt_directory) if prompt_directory else None
        self.prompts: Dict[str, JsonPrompt] = {}
        self.validator = JsonSchemaValidator()
        self.logger = logging.getLogger(__name__)
        
        # Load prompts if directory is provided
        if self.prompt_directory and self.prompt_directory.exists():
            self.load_all_prompts()
    
    def load_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """
        Load a prompt configuration by ID.
        
        Args:
            prompt_id: The unique identifier for the prompt
            
        Returns:
            The prompt configuration dictionary
            
        Raises:
            FileNotFoundError: If the prompt file is not found
            ValueError: If the prompt configuration is invalid
        """
        if prompt_id in self.prompts:
            return self.prompts[prompt_id].config
        
        # Try to load from file
        if self.prompt_directory:
            prompt_file = self.prompt_directory / f"{prompt_id}.json"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Validate and cache
                prompt = JsonPrompt(config)
                self.prompts[prompt_id] = prompt
                return config
        
        raise FileNotFoundError(f"Prompt not found: {prompt_id}")
    
    def load_all_prompts(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all available prompt configurations.
        
        Returns:
            Dictionary mapping prompt IDs to their configurations
        """
        all_configs = {}
        
        if not self.prompt_directory or not self.prompt_directory.exists():
            self.logger.warning("Prompt directory not found or not set")
            return all_configs
        
        # Load all JSON files in the directory
        for prompt_file in self.prompt_directory.glob("*.json"):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Validate configuration
                validation_result = self.validator.validate_schema(config)
                if not validation_result.is_valid:
                    self.logger.error(f"Invalid prompt configuration in {prompt_file}: {validation_result.errors}")
                    continue
                
                # Create and cache prompt
                prompt = JsonPrompt(config)
                prompt_id = config["id"]
                self.prompts[prompt_id] = prompt
                all_configs[prompt_id] = config
                
                self.logger.debug(f"Loaded prompt: {prompt_id}")
                
            except Exception as e:
                self.logger.error(f"Error loading prompt from {prompt_file}: {str(e)}")
        
        self.logger.info(f"Loaded {len(all_configs)} prompts")
        return all_configs
    
    def get_prompt(self, prompt_id: str, variant: Optional[str] = None) -> JsonPrompt:
        """
        Get a prompt instance by ID, optionally with a variant.
        
        Args:
            prompt_id: The unique identifier for the prompt
            variant: Optional variant condition
            
        Returns:
            JsonPrompt instance
            
        Raises:
            KeyError: If the prompt is not found
        """
        if prompt_id not in self.prompts:
            # Try to load it
            self.load_prompt(prompt_id)
        
        base_prompt = self.prompts[prompt_id]
        
        if variant:
            variant_prompt = base_prompt.get_variant(variant)
            if variant_prompt:
                return variant_prompt
            else:
                self.logger.warning(f"Variant '{variant}' not found for prompt '{prompt_id}', using base prompt")
        
        return base_prompt
    
    def execute(self, prompt_id: str, parameters: Dict[str, Any], variant: Optional[str] = None) -> PromptResult:
        """
        Execute a prompt with the given parameters.
        
        Args:
            prompt_id: The unique identifier for the prompt
            parameters: Dictionary of parameter values
            variant: Optional variant condition
            
        Returns:
            PromptResult with the rendered prompt and metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Get the prompt
            prompt = self.get_prompt(prompt_id, variant)
            
            # Validate parameters
            validation_result = prompt.validate_input(parameters)
            
            # Render the prompt
            rendered_prompt = prompt.render(parameters)
            
            execution_time = time.time() - start_time
            
            return PromptResult(
                rendered_prompt=rendered_prompt,
                parameters_used=parameters,
                model_type=prompt.model_type,
                execution_time=execution_time,
                validation_result=validation_result
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_result = ValidationResult(
                is_valid=False,
                errors=[f"Execution failed: {str(e)}"]
            )
            
            return PromptResult(
                rendered_prompt="",
                parameters_used=parameters,
                model_type=ModelType.STANDARD,
                execution_time=execution_time,
                validation_result=error_result
            )
    
    def get_variants(self, prompt_id: str) -> List[str]:
        """
        Get available variants for a prompt.
        
        Args:
            prompt_id: The unique identifier for the prompt
            
        Returns:
            List of variant names
        """
        if prompt_id not in self.prompts:
            try:
                self.load_prompt(prompt_id)
            except FileNotFoundError:
                return []
        
        prompt = self.prompts[prompt_id]
        return [variant.name for variant in prompt.variants]
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List all available prompts with their metadata.
        
        Returns:
            List of prompt metadata dictionaries
        """
        prompt_list = []
        
        for prompt_id, prompt in self.prompts.items():
            metadata = {
                "id": prompt.id,
                "name": prompt.name,
                "version": prompt.version,
                "task": prompt.task,
                "topic": prompt.topic,
                "category": prompt.category,
                "model_type": prompt.model_type.value,
                "format": prompt.format,
                "parameter_count": len(prompt.parameters),
                "has_variants": len(prompt.variants) > 0,
                "example_count": len(prompt.examples)
            }
            prompt_list.append(metadata)
        
        return prompt_list
    
    def validate_prompt(self, prompt_id: str) -> ValidationResult:
        """
        Validate a specific prompt configuration.
        
        Args:
            prompt_id: The unique identifier for the prompt
            
        Returns:
            ValidationResult with validation status and any errors
        """
        try:
            if prompt_id not in self.prompts:
                self.load_prompt(prompt_id)
            
            prompt = self.prompts[prompt_id]
            return ValidationResult(is_valid=True, errors=[], warnings=[])
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {str(e)}"]
            )
    
    def reload_prompts(self) -> int:
        """
        Reload all prompts from the directory.
        
        Returns:
            Number of prompts loaded
        """
        self.prompts.clear()
        configs = self.load_all_prompts()
        return len(configs)
    
    def add_prompt(self, config: Dict[str, Any]) -> None:
        """
        Add a new prompt configuration.
        
        Args:
            config: The prompt configuration dictionary
            
        Raises:
            ValueError: If the configuration is invalid
        """
        prompt = JsonPrompt(config)
        self.prompts[prompt.id] = prompt
        self.logger.info(f"Added prompt: {prompt.id}")
    
    def remove_prompt(self, prompt_id: str) -> bool:
        """
        Remove a prompt from the manager.
        
        Args:
            prompt_id: The unique identifier for the prompt
            
        Returns:
            True if the prompt was removed, False if it wasn't found
        """
        if prompt_id in self.prompts:
            del self.prompts[prompt_id]
            self.logger.info(f"Removed prompt: {prompt_id}")
            return True
        return False
    
    def get_prompts_by_category(self, category: str) -> List[JsonPrompt]:
        """
        Get all prompts in a specific category.
        
        Args:
            category: The category to filter by
            
        Returns:
            List of JsonPrompt instances in the category
        """
        return [
            prompt for prompt in self.prompts.values()
            if prompt.category == category
        ]
    
    def get_prompts_by_task(self, task: str) -> List[JsonPrompt]:
        """
        Get all prompts for a specific task.
        
        Args:
            task: The task to filter by
            
        Returns:
            List of JsonPrompt instances for the task
        """
        return [
            prompt for prompt in self.prompts.values()
            if prompt.task == task
        ]
    
    def get_prompts_by_model_type(self, model_type: ModelType) -> List[JsonPrompt]:
        """
        Get all prompts compatible with a specific model type.
        
        Args:
            model_type: The model type to filter by
            
        Returns:
            List of JsonPrompt instances compatible with the model type
        """
        return [
            prompt for prompt in self.prompts.values()
            if prompt.model_type == model_type or prompt.model_type == ModelType.BOTH
        ]