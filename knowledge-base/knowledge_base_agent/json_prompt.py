"""
JSON Prompt Management System

This module provides the core JsonPrompt class for loading, validating, and rendering
JSON-based prompt configurations. It supports both standard and reasoning model formats
with parameter validation, template rendering, and conditional logic.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import jsonschema
from jinja2 import Template, Environment, BaseLoader, TemplateError


class JsonPromptError(Exception):
    """Base exception for JSON prompt system errors."""
    pass


class JsonPromptValidationError(JsonPromptError):
    """Raised when prompt validation fails."""
    pass


class JsonPromptRenderError(JsonPromptError):
    """Raised when prompt rendering fails."""
    pass


@dataclass
class PromptRenderResult:
    """Result of prompt rendering operation."""
    content: Union[str, Dict[str, str]]  # String for standard, Dict for reasoning
    model_type: str
    prompt_id: str
    parameters_used: Dict[str, Any]
    render_time_ms: float
    warnings: List[str]


class JsonPrompt:
    """
    Core class for loading and managing individual JSON prompt configurations.
    
    Provides parameter validation, template rendering, conditional logic support,
    and comprehensive error handling for JSON-based prompts.
    """
    
    def __init__(self, prompt_file: Union[str, Path, Dict[str, Any]], schema_file: Optional[Union[str, Path]] = None):
        """
        Initialize JsonPrompt from file path or dictionary.
        
        Args:
            prompt_file: Path to JSON prompt file or prompt dictionary
            schema_file: Optional path to JSON schema file for validation
        """
        self.prompt_data: Dict[str, Any] = {}
        self.schema: Optional[Dict[str, Any]] = None
        self.template_env = Environment(loader=BaseLoader())
        self.validation_errors: List[str] = []
        
        # Load prompt data
        if isinstance(prompt_file, (str, Path)):
            self.prompt_file = Path(prompt_file)
            self._load_from_file()
        elif isinstance(prompt_file, dict):
            self.prompt_file = None
            self.prompt_data = prompt_file
        else:
            raise JsonPromptError(f"Invalid prompt_file type: {type(prompt_file)}")
        
        # Load schema if provided
        if schema_file:
            self._load_schema(schema_file)
            
        # Validate prompt data
        self._validate_prompt_data()
        
        # Setup template environment with custom filters
        self._setup_template_environment()
    
    def _load_from_file(self) -> None:
        """Load prompt data from JSON file."""
        try:
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                self.prompt_data = json.load(f)
        except FileNotFoundError:
            raise JsonPromptError(f"Prompt file not found: {self.prompt_file}")
        except json.JSONDecodeError as e:
            raise JsonPromptError(f"Invalid JSON in prompt file {self.prompt_file}: {e}")
    
    def _load_schema(self, schema_file: Union[str, Path]) -> None:
        """Load JSON schema for validation."""
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                self.schema = json.load(f)
        except FileNotFoundError:
            raise JsonPromptError(f"Schema file not found: {schema_file}")
        except json.JSONDecodeError as e:
            raise JsonPromptError(f"Invalid JSON in schema file {schema_file}: {e}")
    
    def _validate_prompt_data(self) -> None:
        """Validate prompt data against schema and business rules."""
        self.validation_errors = []
        
        # Schema validation if schema is loaded
        if self.schema:
            try:
                jsonschema.validate(self.prompt_data, self.schema)
            except jsonschema.ValidationError as e:
                self.validation_errors.append(f"Schema validation error: {e.message}")
        
        # Business rule validation
        self._validate_business_rules()
        
        if self.validation_errors:
            raise JsonPromptValidationError(f"Prompt validation failed: {'; '.join(self.validation_errors)}")
    
    def _validate_business_rules(self) -> None:
        """Validate business-specific rules."""
        # Check required fields
        required_fields = ['prompt_id', 'prompt_name', 'description', 'model_type', 'category', 'task', 'input_parameters', 'template']
        for field in required_fields:
            if field not in self.prompt_data:
                self.validation_errors.append(f"Missing required field: {field}")
        
        # Validate model_type
        if 'model_type' in self.prompt_data:
            if self.prompt_data['model_type'] not in ['standard', 'reasoning']:
                self.validation_errors.append(f"Invalid model_type: {self.prompt_data['model_type']}")
        
        # Validate template structure based on model type
        if 'template' in self.prompt_data and 'model_type' in self.prompt_data:
            self._validate_template_structure()
        
        # Validate input parameters
        if 'input_parameters' in self.prompt_data:
            self._validate_input_parameters()
    
    def _validate_template_structure(self) -> None:
        """Validate template structure matches model type."""
        template = self.prompt_data['template']
        model_type = self.prompt_data['model_type']
        
        if model_type == 'standard':
            if 'content' not in template:
                self.validation_errors.append("Standard model template must have 'content' field")
        elif model_type == 'reasoning':
            if 'system_message' not in template or 'user_message' not in template:
                self.validation_errors.append("Reasoning model template must have 'system_message' and 'user_message' fields")
    
    def _validate_input_parameters(self) -> None:
        """Validate input parameter definitions."""
        params = self.prompt_data['input_parameters']
        
        if 'required' not in params or 'parameters' not in params:
            self.validation_errors.append("input_parameters must have 'required' and 'parameters' fields")
            return
        
        # Check that all required parameters are defined
        for req_param in params.get('required', []):
            if req_param not in params.get('parameters', {}):
                self.validation_errors.append(f"Required parameter '{req_param}' not defined in parameters")
        
        # Check that all optional parameters are defined
        for opt_param in params.get('optional', []):
            if opt_param not in params.get('parameters', {}):
                self.validation_errors.append(f"Optional parameter '{opt_param}' not defined in parameters")
    
    def _setup_template_environment(self) -> None:
        """Setup Jinja2 template environment with custom filters."""
        def replace_filter(text: str, old: str, new: str) -> str:
            """Custom filter for string replacement."""
            return text.replace(old, new)
        
        def conditional_text(condition: bool, true_text: str, false_text: str = "") -> str:
            """Custom filter for conditional text."""
            return true_text if condition else false_text
        
        self.template_env.filters['replace'] = replace_filter
        self.template_env.filters['conditional'] = conditional_text
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """
        Validate input parameters against prompt requirements.
        
        Args:
            parameters: Dictionary of parameter values
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        param_config = self.prompt_data.get('input_parameters', {})
        required_params = param_config.get('required', [])
        param_definitions = param_config.get('parameters', {})
        
        # Check required parameters
        for req_param in required_params:
            if req_param not in parameters:
                errors.append(f"Missing required parameter: {req_param}")
        
        # Validate parameter types and constraints
        for param_name, param_value in parameters.items():
            if param_name in param_definitions:
                param_def = param_definitions[param_name]
                errors.extend(self._validate_parameter_value(param_name, param_value, param_def))
        
        return errors
    
    def _validate_parameter_value(self, name: str, value: Any, definition: Dict[str, Any]) -> List[str]:
        """Validate a single parameter value against its definition."""
        errors = []
        expected_type = definition.get('type', 'string')
        
        # Type validation
        type_map = {
            'string': str,
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
            'dict': dict
        }
        
        if expected_type in type_map:
            expected_python_type = type_map[expected_type]
            if not isinstance(value, expected_python_type):
                errors.append(f"Parameter '{name}' must be of type {expected_type}, got {type(value).__name__}")
        
        # Additional validation rules
        validation = definition.get('validation', {})
        if isinstance(value, str):
            if 'pattern' in validation:
                if not re.match(validation['pattern'], value):
                    errors.append(f"Parameter '{name}' does not match required pattern: {validation['pattern']}")
            if 'min_length' in validation and len(value) < validation['min_length']:
                errors.append(f"Parameter '{name}' must be at least {validation['min_length']} characters")
            if 'max_length' in validation and len(value) > validation['max_length']:
                errors.append(f"Parameter '{name}' must be at most {validation['max_length']} characters")
        
        if 'enum' in validation:
            if value not in validation['enum']:
                errors.append(f"Parameter '{name}' must be one of: {validation['enum']}")
        
        return errors
    
    def render(self, parameters: Dict[str, Any], variant: Optional[str] = None) -> PromptRenderResult:
        """
        Render the prompt with given parameters.
        
        Args:
            parameters: Dictionary of parameter values
            variant: Optional variant name to use instead of default template
            
        Returns:
            PromptRenderResult with rendered content and metadata
        """
        start_time = datetime.now()
        warnings = []
        
        # Validate parameters
        validation_errors = self.validate_parameters(parameters)
        if validation_errors:
            raise JsonPromptRenderError(f"Parameter validation failed: {'; '.join(validation_errors)}")
        
        # Add default values for missing optional parameters
        param_config = self.prompt_data.get('input_parameters', {})
        param_definitions = param_config.get('parameters', {})
        final_parameters = parameters.copy()
        
        for param_name, param_def in param_definitions.items():
            if param_name not in final_parameters and 'default' in param_def:
                final_parameters[param_name] = param_def['default']
        
        # Select template (variant or default)
        template_config = self._select_template(final_parameters, variant)
        
        # Add computed parameters
        final_parameters.update(self._compute_dynamic_parameters(final_parameters))
        
        try:
            # Render based on model type
            if self.prompt_data['model_type'] == 'standard':
                content = self._render_standard_template(template_config, final_parameters)
            else:  # reasoning
                content = self._render_reasoning_template(template_config, final_parameters)
            
            # Calculate render time
            end_time = datetime.now()
            render_time_ms = (end_time - start_time).total_seconds() * 1000
            
            return PromptRenderResult(
                content=content,
                model_type=self.prompt_data['model_type'],
                prompt_id=self.prompt_data['prompt_id'],
                parameters_used=final_parameters,
                render_time_ms=render_time_ms,
                warnings=warnings
            )
            
        except TemplateError as e:
            raise JsonPromptRenderError(f"Template rendering failed: {e}")
        except Exception as e:
            raise JsonPromptRenderError(f"Unexpected error during rendering: {e}")
    
    def _select_template(self, parameters: Dict[str, Any], variant: Optional[str] = None) -> Dict[str, Any]:
        """Select appropriate template based on variant or conditions."""
        if variant:
            # Look for specific variant
            variants = self.prompt_data.get('variants', [])
            for v in variants:
                if v['name'] == variant:
                    return v['template']
            raise JsonPromptRenderError(f"Variant '{variant}' not found")
        
        # Check for conditional variants
        variants = self.prompt_data.get('variants', [])
        for v in variants:
            if self._evaluate_condition(v.get('condition', ''), parameters):
                return v['template']
        
        # Return default template
        return self.prompt_data['template']
    
    def _evaluate_condition(self, condition: str, parameters: Dict[str, Any]) -> bool:
        """Evaluate a simple condition string against parameters."""
        if not condition:
            return False
        
        # Simple condition evaluation (can be extended)
        # Supports: param_name == value, param_name != value, param_name == true/false
        try:
            # Replace parameter names with their values
            eval_condition = condition
            for param_name, param_value in parameters.items():
                if isinstance(param_value, str):
                    eval_condition = eval_condition.replace(param_name, f"'{param_value}'")
                else:
                    eval_condition = eval_condition.replace(param_name, str(param_value))
            
            # Simple evaluation (security note: in production, use a safer evaluator)
            return eval(eval_condition)
        except:
            return False
    
    def _compute_dynamic_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Compute dynamic parameters based on input parameters."""
        computed = {}
        
        # Example: source_type_indicator for categorization prompts
        if 'is_thread' in parameters:
            computed['source_type_indicator'] = "Tweet Thread Content" if parameters['is_thread'] else "Tweet Content"
        
        # Complex processing for KB item generation prompts
        if 'context_data' in parameters:
            computed.update(self._process_kb_item_context_data(parameters['context_data']))
        
        # Synthesis mode instruction processing
        if 'synthesis_mode' in parameters:
            computed['mode_instruction'] = self._get_synthesis_mode_instruction(parameters['synthesis_mode'])
        
        # README statistics processing
        if 'kb_stats' in parameters:
            computed.update(self._process_kb_stats(parameters['kb_stats']))
        
        # README category description processing
        if 'active_subcats' in parameters:
            computed.update(self._process_category_description(parameters))
        
        # Reasoning KB item generation processing
        if 'categories' in parameters:
            computed.update(self._process_reasoning_kb_categories(parameters))
        
        # Media descriptions processing
        if 'media_descriptions' in parameters:
            computed['media_desc_text'] = self._process_media_descriptions(parameters['media_descriptions'])
        
        return computed
    
    def _process_kb_item_context_data(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process complex context_data for KB item generation prompts."""
        computed = {}
        
        # Extract basic fields
        computed['main_category'] = context_data.get('main_category', 'N/A')
        computed['sub_category'] = context_data.get('sub_category', 'N/A')
        computed['item_name_hint'] = context_data.get('item_name', 'N/A')
        
        # Process tweet content
        tweet_segments = context_data.get('tweet_segments', [])
        single_tweet_text = context_data.get('tweet_text', '')
        
        source_content_md = ""
        if tweet_segments:
            source_content_md += "**Source Information (Tweet Thread):**\\n"
            for i, segment_text in enumerate(tweet_segments):
                source_content_md += f"- Segment {i+1}: \"{segment_text}\"\\n"
            source_content_md += "\\n"
        elif single_tweet_text:
            source_content_md += "**Source Information (Single Tweet):**\\n"
            source_content_md += f"- Tweet Text: \"{single_tweet_text}\"\\n\\n"
        
        computed['source_content_md'] = source_content_md
        
        # Process media descriptions
        all_media_descriptions = context_data.get('all_media_descriptions', [])
        media_context_md = ""
        if all_media_descriptions:
            media_context_md += "Associated Media Insights (derived from all images/videos in the thread/tweet):\\n"
            for i, desc in enumerate(all_media_descriptions):
                media_context_md += f"- Media {i+1}: {desc}\\n"
            media_context_md += "\\n"
        
        computed['media_context_md'] = media_context_md
        
        # Process URLs
        all_urls = context_data.get('all_urls', [])
        urls_context_md = ""
        if all_urls:
            urls_context_md += "Mentioned URLs (from all segments in the thread/tweet, for context, not necessarily for inclusion as external_references unless very specific and high-value):\\n"
            for url in all_urls:
                urls_context_md += f"- {url}\\n"
            urls_context_md += "\\n"
        
        computed['urls_context_md'] = urls_context_md
        
        return computed
    
    def _get_synthesis_mode_instruction(self, synthesis_mode: str) -> str:
        """Get instruction text for synthesis mode."""
        mode_instructions = {
            "comprehensive": "Create a comprehensive synthesis that covers all major patterns, concepts, and insights.",
            "technical_deep_dive": "Focus on deep technical analysis, architectural patterns, and expert-level implementation details.",
            "practical_guide": "Emphasize practical applications, real-world use cases, and actionable guidance."
        }
        return mode_instructions.get(synthesis_mode, mode_instructions["comprehensive"])
    
    def _process_kb_stats(self, kb_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Process knowledge base statistics for README generation."""
        computed = {}
        
        # Extract individual statistics
        computed['kb_items'] = kb_stats.get('total_items', 0)
        computed['synthesis_docs'] = kb_stats.get('total_synthesis', 0)
        computed['total_content'] = kb_stats.get('total_combined', computed['kb_items'] + computed['synthesis_docs'])
        computed['total_main_cats'] = kb_stats.get('total_main_cats', 0)
        computed['total_subcats'] = kb_stats.get('total_subcats', 0)
        computed['total_media'] = kb_stats.get('total_media', 0)
        
        return computed
    
    def _process_category_description(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process category description parameters."""
        computed = {}
        
        active_subcats = parameters.get('active_subcats', [])
        computed['subcategory_count'] = len(active_subcats)
        computed['formatted_subcats'] = ', '.join(sub.replace('_', ' ').title() for sub in active_subcats)
        
        return computed
    
    def _process_reasoning_kb_categories(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process categories for reasoning KB item generation."""
        computed = {}
        categories = parameters.get('categories', {})
        
        computed['main_category'] = categories.get('main_category', '')
        computed['sub_category'] = categories.get('sub_category', '')
        computed['item_name'] = categories.get('item_name', '')
        
        return computed
    
    def _process_media_descriptions(self, media_descriptions: List[str]) -> str:
        """Process media descriptions into formatted text."""
        if not media_descriptions or len(media_descriptions) == 0:
            return ""
        
        return "\\n\\nMedia Descriptions:\\n" + "\\n".join([f"- {desc}" for desc in media_descriptions])
    
    def _render_standard_template(self, template_config: Dict[str, Any], parameters: Dict[str, Any]) -> str:
        """Render standard model template."""
        template_str = template_config.get('content', '')
        template = self.template_env.from_string(template_str)
        return template.render(**parameters)
    
    def _render_reasoning_template(self, template_config: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, str]:
        """Render reasoning model template."""
        system_template = self.template_env.from_string(template_config.get('system_message', ''))
        user_template = self.template_env.from_string(template_config.get('user_message', ''))
        
        # For reasoning prompts, we need to determine which message to return based on the prompt type
        # System message prompts should return system role, others return user role
        if self.prompt_id == "system_message":
            return {
                'role': 'system',
                'content': system_template.render(**parameters)
            }
        else:
            return {
                'role': 'user',
                'content': user_template.render(**parameters)
            }
    
    # Property accessors for prompt metadata
    @property
    def prompt_id(self) -> str:
        return self.prompt_data.get('prompt_id', '')
    
    @property
    def prompt_name(self) -> str:
        return self.prompt_data.get('prompt_name', '')
    
    @property
    def description(self) -> str:
        return self.prompt_data.get('description', '')
    
    @property
    def model_type(self) -> str:
        return self.prompt_data.get('model_type', 'standard')
    
    @property
    def category(self) -> str:
        return self.prompt_data.get('category', '')
    
    @property
    def task(self) -> str:
        return self.prompt_data.get('task', '')
    
    @property
    def required_parameters(self) -> List[str]:
        return self.prompt_data.get('input_parameters', {}).get('required', [])
    
    @property
    def optional_parameters(self) -> List[str]:
        return self.prompt_data.get('input_parameters', {}).get('optional', [])
    
    @property
    def all_parameters(self) -> List[str]:
        return self.required_parameters + self.optional_parameters
    
    @property
    def variants(self) -> List[str]:
        return [v['name'] for v in self.prompt_data.get('variants', [])]
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return self.prompt_data.get('metadata', {})
    
    def get_parameter_info(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific parameter."""
        params = self.prompt_data.get('input_parameters', {}).get('parameters', {})
        return params.get(parameter_name)
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Get example inputs and outputs for this prompt."""
        return self.prompt_data.get('examples', [])
    
    def to_dict(self) -> Dict[str, Any]:
        """Return the complete prompt data as a dictionary."""
        return self.prompt_data.copy()