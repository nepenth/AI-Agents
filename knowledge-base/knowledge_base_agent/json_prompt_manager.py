"""
JSON Prompt Management System

This module provides the JsonPromptManager class for runtime operations including
prompt loading, caching, environment-based configuration, and prompt execution.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

from .json_prompt import JsonPrompt, JsonPromptError, PromptRenderResult
from .config import Config


logger = logging.getLogger(__name__)


@dataclass
class PromptCacheEntry:
    """Cache entry for loaded prompts."""
    prompt: JsonPrompt
    loaded_at: datetime
    file_path: Path
    file_mtime: float


class JsonPromptManagerError(Exception):
    """Base exception for JsonPromptManager errors."""
    pass


class JsonPromptManager:
    """
    Runtime management system for JSON-based prompts.
    
    Provides prompt loading, caching, environment-based configuration,
    and comprehensive prompt execution capabilities.
    """
    
    def __init__(self, config: Optional[Config] = None, prompts_dir: Optional[Union[str, Path]] = None):
        """
        Initialize JsonPromptManager.
        
        Args:
            config: Optional Config object for environment-based configuration
            prompts_dir: Optional custom prompts directory path
        """
        self.config = config
        self.prompts_dir = self._resolve_prompts_directory(prompts_dir)
        self.schema_file = self.prompts_dir.parent / "prompt_schema.json"
        
        # Cache management
        self._prompt_cache: Dict[str, PromptCacheEntry] = {}
        self._cache_lock = threading.RLock()
        self._config_cache: Optional[Dict[str, Any]] = None
        
        # Performance tracking
        self._load_stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'load_errors': 0,
            'total_renders': 0
        }
        
        # Load configuration
        self._load_configuration()
        
        logger.info(f"JsonPromptManager initialized with prompts directory: {self.prompts_dir}")
    
    def _resolve_prompts_directory(self, prompts_dir: Optional[Union[str, Path]]) -> Path:
        """Resolve the prompts directory path."""
        if prompts_dir:
            return Path(prompts_dir).resolve()
        
        # Default to prompts_json directory relative to this module
        module_dir = Path(__file__).parent
        return (module_dir / "prompts_json").resolve()
    
    def _load_configuration(self) -> None:
        """Load prompt system configuration."""
        config_file = self.prompts_dir / "config.json"
        
        if not config_file.exists():
            logger.warning(f"Configuration file not found: {config_file}")
            self._config_cache = {}
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
            logger.info("Prompt system configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._config_cache = {}
    
    def get_available_prompts(self) -> Dict[str, List[str]]:
        """
        Get list of available prompts organized by model type.
        
        Returns:
            Dictionary with model types as keys and lists of prompt IDs as values
        """
        available = {"standard": [], "reasoning": []}
        
        for model_type in ["standard", "reasoning"]:
            model_dir = self.prompts_dir / model_type
            if model_dir.exists():
                for prompt_file in model_dir.glob("*.json"):
                    try:
                        # Extract prompt ID from filename or load to get ID
                        prompt_id = prompt_file.stem
                        available[model_type].append(prompt_id)
                    except Exception as e:
                        logger.warning(f"Failed to process prompt file {prompt_file}: {e}")
        
        return available
    
    def load_prompt(self, prompt_id: str, model_type: str = "standard", force_reload: bool = False) -> JsonPrompt:
        """
        Load a prompt by ID and model type.
        
        Args:
            prompt_id: Unique identifier for the prompt
            model_type: Model type ("standard" or "reasoning")
            force_reload: Force reload even if cached
            
        Returns:
            JsonPrompt instance
            
        Raises:
            JsonPromptManagerError: If prompt cannot be loaded
        """
        cache_key = f"{model_type}:{prompt_id}"
        
        with self._cache_lock:
            # Check cache first
            if not force_reload and cache_key in self._prompt_cache:
                cache_entry = self._prompt_cache[cache_key]
                
                # Check if file has been modified
                if cache_entry.file_path.exists():
                    current_mtime = cache_entry.file_path.stat().st_mtime
                    if current_mtime == cache_entry.file_mtime:
                        self._load_stats['cache_hits'] += 1
                        logger.debug(f"Cache hit for prompt: {cache_key}")
                        return cache_entry.prompt
                
                # File modified, remove from cache
                del self._prompt_cache[cache_key]
            
            # Load from file
            self._load_stats['cache_misses'] += 1
            
            try:
                prompt_file = self._find_prompt_file(prompt_id, model_type)
                if not prompt_file:
                    raise JsonPromptManagerError(f"Prompt file not found: {prompt_id} ({model_type})")
                
                # Load prompt
                prompt = JsonPrompt(prompt_file, self.schema_file)
                
                # Cache the loaded prompt
                cache_entry = PromptCacheEntry(
                    prompt=prompt,
                    loaded_at=datetime.now(),
                    file_path=prompt_file,
                    file_mtime=prompt_file.stat().st_mtime
                )
                self._prompt_cache[cache_key] = cache_entry
                
                logger.debug(f"Loaded and cached prompt: {cache_key}")
                return prompt
                
            except Exception as e:
                self._load_stats['load_errors'] += 1
                logger.error(f"Failed to load prompt {cache_key}: {e}")
                raise JsonPromptManagerError(f"Failed to load prompt {cache_key}: {e}")
    
    def _find_prompt_file(self, prompt_id: str, model_type: str) -> Optional[Path]:
        """Find the prompt file for given ID and model type."""
        model_dir = self.prompts_dir / model_type
        
        if not model_dir.exists():
            return None
        
        # Try exact filename match
        exact_file = model_dir / f"{prompt_id}.json"
        if exact_file.exists():
            return exact_file
        
        # Search for files containing the prompt_id
        for prompt_file in model_dir.glob("*.json"):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('prompt_id') == prompt_id:
                        return prompt_file
            except Exception:
                continue
        
        return None
    
    def render_prompt(self, prompt_id: str, parameters: Dict[str, Any], 
                     model_type: str = "standard", variant: Optional[str] = None) -> PromptRenderResult:
        """
        Render a prompt with given parameters.
        
        Args:
            prompt_id: Unique identifier for the prompt
            parameters: Dictionary of parameter values
            model_type: Model type ("standard" or "reasoning")
            variant: Optional variant name to use
            
        Returns:
            PromptRenderResult with rendered content and metadata
            
        Raises:
            JsonPromptManagerError: If prompt cannot be rendered
        """
        try:
            prompt = self.load_prompt(prompt_id, model_type)
            result = prompt.render(parameters, variant)
            
            self._load_stats['total_renders'] += 1
            logger.debug(f"Rendered prompt {prompt_id} in {result.render_time_ms:.2f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to render prompt {prompt_id}: {e}")
            raise JsonPromptManagerError(f"Failed to render prompt {prompt_id}: {e}")
    
    def get_prompt_info(self, prompt_id: str, model_type: str = "standard") -> Dict[str, Any]:
        """
        Get detailed information about a prompt.
        
        Args:
            prompt_id: Unique identifier for the prompt
            model_type: Model type ("standard" or "reasoning")
            
        Returns:
            Dictionary with prompt information
        """
        try:
            prompt = self.load_prompt(prompt_id, model_type)
            
            return {
                'prompt_id': prompt.prompt_id,
                'prompt_name': prompt.prompt_name,
                'description': prompt.description,
                'model_type': prompt.model_type,
                'category': prompt.category,
                'task': prompt.task,
                'required_parameters': prompt.required_parameters,
                'optional_parameters': prompt.optional_parameters,
                'variants': prompt.variants,
                'examples': prompt.get_examples(),
                'metadata': prompt.metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to get prompt info for {prompt_id}: {e}")
            raise JsonPromptManagerError(f"Failed to get prompt info for {prompt_id}: {e}")
    
    def validate_prompt(self, prompt_id: str, model_type: str = "standard") -> Dict[str, Any]:
        """
        Validate a prompt and return validation results.
        
        Args:
            prompt_id: Unique identifier for the prompt
            model_type: Model type ("standard" or "reasoning")
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'prompt_id': prompt_id,
            'model_type': model_type,
            'valid': False,
            'errors': [],
            'warnings': [],
            'schema_valid': False,
            'examples_valid': False
        }
        
        try:
            prompt = self.load_prompt(prompt_id, model_type)
            validation_result['valid'] = True
            validation_result['schema_valid'] = True
            
            # Test examples if available
            examples = prompt.get_examples()
            if examples:
                example_errors = []
                for i, example in enumerate(examples):
                    try:
                        prompt.render(example['input'])
                    except Exception as e:
                        example_errors.append(f"Example {i+1} ({example['name']}): {e}")
                
                if example_errors:
                    validation_result['errors'].extend(example_errors)
                else:
                    validation_result['examples_valid'] = True
            else:
                validation_result['examples_valid'] = True  # No examples to validate
            
        except Exception as e:
            validation_result['errors'].append(str(e))
        
        return validation_result
    
    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        with self._cache_lock:
            self._prompt_cache.clear()
            logger.info("Prompt cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache and performance statistics."""
        with self._cache_lock:
            return {
                'cached_prompts': len(self._prompt_cache),
                'cache_hits': self._load_stats['cache_hits'],
                'cache_misses': self._load_stats['cache_misses'],
                'load_errors': self._load_stats['load_errors'],
                'total_renders': self._load_stats['total_renders'],
                'hit_rate': (
                    self._load_stats['cache_hits'] / 
                    max(1, self._load_stats['cache_hits'] + self._load_stats['cache_misses'])
                ) * 100
            }
    
    def preload_prompts(self, model_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Preload prompts for better performance.
        
        Args:
            model_types: List of model types to preload (default: all)
            
        Returns:
            Dictionary with preload results
        """
        if model_types is None:
            model_types = ["standard", "reasoning"]
        
        results = {
            'loaded': 0,
            'errors': 0,
            'details': []
        }
        
        available_prompts = self.get_available_prompts()
        
        for model_type in model_types:
            if model_type not in available_prompts:
                continue
                
            for prompt_id in available_prompts[model_type]:
                try:
                    self.load_prompt(prompt_id, model_type)
                    results['loaded'] += 1
                    results['details'].append(f"✅ {model_type}:{prompt_id}")
                except Exception as e:
                    results['errors'] += 1
                    results['details'].append(f"❌ {model_type}:{prompt_id} - {e}")
        
        logger.info(f"Preloaded {results['loaded']} prompts with {results['errors']} errors")
        return results
    
    def search_prompts(self, query: str, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search prompts by query string.
        
        Args:
            query: Search query (searches in name, description, tags)
            model_type: Optional model type filter
            
        Returns:
            List of matching prompt information
        """
        results = []
        available_prompts = self.get_available_prompts()
        
        model_types = [model_type] if model_type else ["standard", "reasoning"]
        
        for mt in model_types:
            if mt not in available_prompts:
                continue
                
            for prompt_id in available_prompts[mt]:
                try:
                    info = self.get_prompt_info(prompt_id, mt)
                    
                    # Search in various fields
                    searchable_text = " ".join([
                        info.get('prompt_name', ''),
                        info.get('description', ''),
                        info.get('task', ''),
                        " ".join(info.get('metadata', {}).get('tags', []))
                    ]).lower()
                    
                    if query.lower() in searchable_text:
                        results.append(info)
                        
                except Exception as e:
                    logger.warning(f"Failed to search prompt {prompt_id}: {e}")
        
        return results
    
    def get_prompts_by_category(self, category: str, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get prompts by category.
        
        Args:
            category: Category name
            model_type: Optional model type filter
            
        Returns:
            List of prompts in the specified category
        """
        results = []
        available_prompts = self.get_available_prompts()
        
        model_types = [model_type] if model_type else ["standard", "reasoning"]
        
        for mt in model_types:
            if mt not in available_prompts:
                continue
                
            for prompt_id in available_prompts[mt]:
                try:
                    info = self.get_prompt_info(prompt_id, mt)
                    if info.get('category') == category:
                        results.append(info)
                except Exception as e:
                    logger.warning(f"Failed to get category for prompt {prompt_id}: {e}")
        
        return results
    
    def export_prompt_catalog(self, output_file: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Export a catalog of all available prompts.
        
        Args:
            output_file: Optional file to write catalog to
            
        Returns:
            Dictionary with complete prompt catalog
        """
        catalog = {
            'generated_at': datetime.now().isoformat(),
            'prompts_directory': str(self.prompts_dir),
            'total_prompts': 0,
            'model_types': {},
            'categories': {},
            'prompts': []
        }
        
        available_prompts = self.get_available_prompts()
        
        for model_type, prompt_ids in available_prompts.items():
            catalog['model_types'][model_type] = len(prompt_ids)
            
            for prompt_id in prompt_ids:
                try:
                    info = self.get_prompt_info(prompt_id, model_type)
                    catalog['prompts'].append(info)
                    
                    # Track categories
                    category = info.get('category', 'unknown')
                    if category not in catalog['categories']:
                        catalog['categories'][category] = 0
                    catalog['categories'][category] += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to export info for prompt {prompt_id}: {e}")
        
        catalog['total_prompts'] = len(catalog['prompts'])
        
        # Write to file if specified
        if output_file:
            output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
            logger.info(f"Prompt catalog exported to: {output_path}")
        
        return catalog