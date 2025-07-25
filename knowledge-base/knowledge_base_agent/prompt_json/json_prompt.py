"""
Core JsonPrompt class for managing individual JSON prompt configurations.

This module provides the main JsonPrompt class that handles loading, validation,
rendering, and execution of individual JSON prompt configurations.
"""

import json
import re
from typing import Dict, Any, List, Optional
from .base import (
    ValidationResult, PromptResult, ModelType, OutputFormat,
    ParameterSpec, OutputSpec, ExtractField, VariantSpec, ExampleSpec
)
from .schema_validator import JsonSchemaValidator


class JsonPrompt:
    """
    Represents a single JSON prompt configuration with rendering and validation capabilities.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize a JsonPrompt from a configuration dictionary.
        
        Args:
            config: The JSON prompt configuration
        """
        self.config = config
        self.validator = JsonSchemaValidator()
        
        # Parse and validate the configuration
        self._validation_result = self.validator.validate_schema(config)
        if not self._validation_result.is_valid:
            raise ValueError(f"Invalid prompt configuration: {self._validation_result.errors}")
        
        # Extract core properties
        self.id = config["id"]
        self.name = config["name"]
        self.version = config.get("version", "1.0.0")
        self.task = config["task"]
        self.topic = config.get("topic", "")
        self.category = config.get("category", "")
        self.model_type = ModelType(config.get("model_type", "standard"))
        self.text = config["text"]
        self.format = config["format"]
        
        # Parse input specifications
        self.parameters = self._parse_parameters(config["input"]["parameters"])
        
        # Parse output specifications
        self.output_spec = self._parse_output_spec(config["output"])
        
        # Parse optional components
        self.constraints = config.get("constraints", {})
        self.variants = self._parse_variants(config.get("variants", []))
        self.examples = self._parse_examples(config.get("examples", []))
        self.metadata = config.get("metadata", {})
    
    def render(self, parameters: Dict[str, Any]) -> str:
        """
        Render the prompt template with the given parameters.
        
        Args:
            parameters: Dictionary of parameter values
            
        Returns:
            The rendered prompt string
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        validation_result = self.validate_input(parameters)
        if not validation_result.is_valid:
            raise ValueError(f"Invalid parameters: {validation_result.errors}")
        
        # Apply default values for missing optional parameters
        complete_parameters = self._apply_defaults(parameters)
        
        # Render the template
        rendered_text = self._render_template(self.text, complete_parameters)
        
        return rendered_text
    
    def validate_input(self, parameters: Dict[str, Any]) -> ValidationResult:
        """
        Validate input parameters against the parameter specifications.
        
        Args:
            parameters: Dictionary of parameter values
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []
        
        # Check required parameters
        required_params = {p.name for p in self.parameters if p.required}
        provided_params = set(parameters.keys())
        
        missing_params = required_params - provided_params
        if missing_params:
            errors.append(f"Missing required parameters: {', '.join(missing_params)}")
        
        # Check for unexpected parameters
        expected_params = {p.name for p in self.parameters}
        unexpected_params = provided_params - expected_params
        if unexpected_params:
            warnings.append(f"Unexpected parameters: {', '.join(unexpected_params)}")
        
        # Validate individual parameter values
        for param in self.parameters:
            if param.name in parameters:
                param_errors = self._validate_parameter_value(
                    param, parameters[param.name]
                )
                errors.extend(param_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_output(self, output: Any) -> ValidationResult:
        """
        Validate output against the expected format.
        
        Args:
            output: The output to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        return self.validator.validate_output(output, self.output_spec.__dict__)
    
    def get_variant(self, condition: str) -> Optional['JsonPrompt']:
        """
        Get a variant of this prompt based on a condition.
        
        Args:
            condition: The condition to match against variants
            
        Returns:
            A new JsonPrompt instance with variant modifications applied,
            or None if no matching variant is found
        """
        for variant in self.variants:
            if self._evaluate_condition(variant.condition, condition):
                # Create a modified configuration
                modified_config = self.config.copy()
                self._apply_modifications(modified_config, variant.modifications)
                
                return JsonPrompt(modified_config)
        
        return None
    
    def get_examples(self) -> List[ExampleSpec]:
        """Get all examples for this prompt."""
        return self.examples
    
    def get_parameter_spec(self, param_name: str) -> Optional[ParameterSpec]:
        """Get the specification for a specific parameter."""
        for param in self.parameters:
            if param.name == param_name:
                return param
        return None
    
    def _parse_parameters(self, param_configs: List[Dict[str, Any]]) -> List[ParameterSpec]:
        """Parse parameter configurations into ParameterSpec objects."""
        parameters = []
        for config in param_configs:
            param = ParameterSpec(
                name=config["name"],
                type=config["type"],
                required=config["required"],
                description=config["description"],
                validation=config.get("validation"),
                default_value=config.get("default_value")
            )
            parameters.append(param)
        return parameters
    
    def _parse_output_spec(self, output_config: Dict[str, Any]) -> OutputSpec:
        """Parse output configuration into OutputSpec object."""
        extract_fields = []
        if "extract" in output_config:
            extract_fields = self._parse_extract_fields(output_config["extract"])
        
        return OutputSpec(
            format=OutputFormat(output_config["format"]),
            schema=output_config.get("schema"),
            max_words=output_config.get("max_words"),
            extract_fields=extract_fields
        )
    
    def _parse_extract_fields(self, extract_configs: List[Dict[str, Any]]) -> List[ExtractField]:
        """Parse extract field configurations into ExtractField objects."""
        fields = []
        for config in extract_configs:
            sub_extracts = []
            if "sub_extracts" in config and config["sub_extracts"]:
                sub_extracts = self._parse_extract_fields(config["sub_extracts"])
            
            field = ExtractField(
                field=config["field"],
                type=config["type"],
                description=config["description"],
                sub_extracts=sub_extracts
            )
            fields.append(field)
        return fields
    
    def _parse_variants(self, variant_configs: List[Dict[str, Any]]) -> List[VariantSpec]:
        """Parse variant configurations into VariantSpec objects."""
        variants = []
        for config in variant_configs:
            variant = VariantSpec(
                name=config["name"],
                condition=config["condition"],
                modifications=config["modifications"]
            )
            variants.append(variant)
        return variants
    
    def _parse_examples(self, example_configs: List[Dict[str, Any]]) -> List[ExampleSpec]:
        """Parse example configurations into ExampleSpec objects."""
        examples = []
        for config in example_configs:
            example = ExampleSpec(
                input=config["input"],
                expected_output=config["expected_output"],
                description=config.get("description")
            )
            examples.append(example)
        return examples
    
    def _apply_defaults(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for missing optional parameters."""
        complete_parameters = parameters.copy()
        
        for param in self.parameters:
            if param.name not in complete_parameters and param.default_value is not None:
                complete_parameters[param.name] = param.default_value
        
        return complete_parameters
    
    def _render_template(self, template: str, parameters: Dict[str, Any]) -> str:
        """
        Render a template string with parameter substitution.
        
        Supports both simple {param} and conditional {param|default} syntax.
        """
        def replace_param(match):
            param_expr = match.group(1)
            
            # Handle conditional syntax: {param|default}
            if '|' in param_expr:
                param_name, default_value = param_expr.split('|', 1)
                return str(parameters.get(param_name.strip(), default_value.strip()))
            else:
                param_name = param_expr.strip()
                if param_name in parameters:
                    return str(parameters[param_name])
                else:
                    # Leave placeholder if parameter not found
                    return match.group(0)
        
        # Replace parameter placeholders
        rendered = re.sub(r'\{([^}]+)\}', replace_param, template)
        
        return rendered
    
    def _validate_parameter_value(self, param: ParameterSpec, value: Any) -> List[str]:
        """Validate a single parameter value against its specification."""
        errors = []
        
        # Basic type checking
        if param.type == "string" and not isinstance(value, str):
            errors.append(f"Parameter {param.name} should be string, got {type(value).__name__}")
        elif param.type == "integer" and not isinstance(value, int):
            errors.append(f"Parameter {param.name} should be integer, got {type(value).__name__}")
        elif param.type == "boolean" and not isinstance(value, bool):
            errors.append(f"Parameter {param.name} should be boolean, got {type(value).__name__}")
        elif param.type == "array" and not isinstance(value, list):
            errors.append(f"Parameter {param.name} should be array, got {type(value).__name__}")
        elif param.type == "object" and not isinstance(value, dict):
            errors.append(f"Parameter {param.name} should be object, got {type(value).__name__}")
        
        # Custom validation rules
        if param.validation:
            validation_errors = self._apply_validation_rules(param, value)
            errors.extend(validation_errors)
        
        return errors
    
    def _apply_validation_rules(self, param: ParameterSpec, value: Any) -> List[str]:
        """Apply custom validation rules to a parameter value."""
        errors = []
        validation = param.validation
        
        if "min_length" in validation and isinstance(value, str):
            if len(value) < validation["min_length"]:
                errors.append(f"Parameter {param.name} too short (min: {validation['min_length']})")
        
        if "max_length" in validation and isinstance(value, str):
            if len(value) > validation["max_length"]:
                errors.append(f"Parameter {param.name} too long (max: {validation['max_length']})")
        
        if "pattern" in validation and isinstance(value, str):
            if not re.match(validation["pattern"], value):
                errors.append(f"Parameter {param.name} doesn't match required pattern")
        
        if "enum" in validation:
            if value not in validation["enum"]:
                errors.append(f"Parameter {param.name} must be one of: {validation['enum']}")
        
        return errors
    
    def _evaluate_condition(self, condition_expr: str, condition_value: str) -> bool:
        """Evaluate a condition expression against a value."""
        # Simple condition evaluation - can be extended for more complex logic
        if condition_expr == condition_value:
            return True
        
        # Support for simple expressions like "equals:value"
        if ':' in condition_expr:
            operator, expected = condition_expr.split(':', 1)
            if operator == "equals":
                return condition_value == expected
            elif operator == "contains":
                return expected in condition_value
        
        return False
    
    def _apply_modifications(self, config: Dict[str, Any], modifications: Dict[str, Any]) -> None:
        """Apply variant modifications to a configuration."""
        for key, value in modifications.items():
            if key in config:
                if isinstance(config[key], dict) and isinstance(value, dict):
                    # Merge dictionaries
                    config[key].update(value)
                else:
                    # Replace value
                    config[key] = value