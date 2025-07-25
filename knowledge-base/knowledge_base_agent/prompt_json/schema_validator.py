"""
Schema validation for JSON prompts.

This module provides comprehensive validation of JSON prompt configurations
against the defined schema, ensuring data integrity and consistency.
"""

import json
import jsonschema
from typing import Dict, Any, List
from .base import ValidationResult, PromptValidator
from .schema import PROMPT_SCHEMA, REASONING_MESSAGE_SCHEMA


class JsonSchemaValidator(PromptValidator):
    """Validates JSON prompt configurations against the schema."""
    
    def __init__(self):
        """Initialize the validator with compiled schemas."""
        self.prompt_validator = jsonschema.Draft7Validator(PROMPT_SCHEMA)
        self.message_validator = jsonschema.Draft7Validator(REASONING_MESSAGE_SCHEMA)
    
    def validate_schema(self, prompt_config: Dict[str, Any]) -> ValidationResult:
        """
        Validate a prompt configuration against the JSON schema.
        
        Args:
            prompt_config: The prompt configuration to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []
        
        try:
            # Validate against main schema
            schema_errors = list(self.prompt_validator.iter_errors(prompt_config))
            
            for error in schema_errors:
                error_path = " -> ".join(str(p) for p in error.absolute_path)
                error_msg = f"Schema validation error at {error_path}: {error.message}"
                errors.append(error_msg)
            
            # Additional custom validations
            custom_errors, custom_warnings = self._custom_validations(prompt_config)
            errors.extend(custom_errors)
            warnings.extend(custom_warnings)
            
        except Exception as e:
            errors.append(f"Schema validation failed: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_output(self, output: Any, output_spec: Dict[str, Any]) -> ValidationResult:
        """
        Validate prompt output against the expected format.
        
        Args:
            output: The actual output to validate
            output_spec: The expected output specification
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []
        warnings = []
        
        try:
            output_format = output_spec.get("format", "text")
            
            if output_format == "json":
                # Validate JSON structure
                if isinstance(output, str):
                    try:
                        parsed_output = json.loads(output)
                    except json.JSONDecodeError as e:
                        errors.append(f"Invalid JSON output: {str(e)}")
                        return ValidationResult(False, errors, warnings)
                else:
                    parsed_output = output
                
                # Validate against schema if provided
                if "schema" in output_spec and output_spec["schema"]:
                    try:
                        jsonschema.validate(parsed_output, output_spec["schema"])
                    except jsonschema.ValidationError as e:
                        errors.append(f"Output schema validation failed: {e.message}")
                
                # Validate extract fields
                if "extract" in output_spec:
                    extract_errors = self._validate_extract_fields(
                        parsed_output, output_spec["extract"]
                    )
                    errors.extend(extract_errors)
            
            elif output_format == "text":
                if not isinstance(output, str):
                    errors.append("Expected text output, got non-string type")
                
                # Check word count if specified
                if "max_words" in output_spec and output_spec["max_words"]:
                    word_count = len(str(output).split())
                    if word_count > output_spec["max_words"]:
                        warnings.append(
                            f"Output exceeds max words: {word_count} > {output_spec['max_words']}"
                        )
            
        except Exception as e:
            errors.append(f"Output validation failed: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _custom_validations(self, prompt_config: Dict[str, Any]) -> tuple[List[str], List[str]]:
        """
        Perform custom validation checks beyond schema validation.
        
        Args:
            prompt_config: The prompt configuration to validate
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        # Validate parameter references in prompt text
        if "text" in prompt_config and "input" in prompt_config:
            text = prompt_config["text"]
            parameters = prompt_config["input"].get("parameters", [])
            param_names = {p["name"] for p in parameters}
            
            # Find parameter placeholders in text (simple {param} format)
            import re
            placeholders = set(re.findall(r'\{(\w+)\}', text))
            
            # Check for undefined parameters
            undefined_params = placeholders - param_names
            if undefined_params:
                errors.append(f"Undefined parameters in text: {', '.join(undefined_params)}")
            
            # Check for unused parameters
            unused_params = param_names - placeholders
            if unused_params:
                warnings.append(f"Unused parameters defined: {', '.join(unused_params)}")
        
        # Validate model type compatibility
        if "model_type" in prompt_config:
            model_type = prompt_config["model_type"]
            if model_type == "reasoning":
                # Reasoning models should have message format considerations
                if "format" in prompt_config and prompt_config["format"] != "message":
                    warnings.append("Reasoning models typically use message format")
        
        # Validate extract field hierarchy
        if "output" in prompt_config and "extract" in prompt_config["output"]:
            extract_errors = self._validate_extract_hierarchy(prompt_config["output"]["extract"])
            errors.extend(extract_errors)
        
        return errors, warnings
    
    def _validate_extract_fields(self, output: Dict[str, Any], extract_spec: List[Dict[str, Any]]) -> List[str]:
        """
        Validate that output contains expected extract fields.
        
        Args:
            output: The parsed output to validate
            extract_spec: The extract field specifications
            
        Returns:
            List of validation errors
        """
        errors = []
        
        for field_spec in extract_spec:
            field_name = field_spec["field"]
            field_type = field_spec["type"]
            
            if field_name not in output:
                errors.append(f"Missing required extract field: {field_name}")
                continue
            
            field_value = output[field_name]
            
            # Basic type checking
            if field_type == "string" and not isinstance(field_value, str):
                errors.append(f"Field {field_name} should be string, got {type(field_value).__name__}")
            elif field_type == "array" and not isinstance(field_value, list):
                errors.append(f"Field {field_name} should be array, got {type(field_value).__name__}")
            elif field_type == "object" and not isinstance(field_value, dict):
                errors.append(f"Field {field_name} should be object, got {type(field_value).__name__}")
            
            # Validate sub-extracts recursively
            if "sub_extracts" in field_spec and field_spec["sub_extracts"]:
                if isinstance(field_value, dict):
                    sub_errors = self._validate_extract_fields(field_value, field_spec["sub_extracts"])
                    errors.extend(sub_errors)
                elif isinstance(field_value, list) and field_value:
                    # Validate first item as representative
                    if isinstance(field_value[0], dict):
                        sub_errors = self._validate_extract_fields(field_value[0], field_spec["sub_extracts"])
                        errors.extend(sub_errors)
        
        return errors
    
    def _validate_extract_hierarchy(self, extract_spec: List[Dict[str, Any]]) -> List[str]:
        """
        Validate the hierarchy and structure of extract field specifications.
        
        Args:
            extract_spec: The extract field specifications to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        field_names = set()
        
        for field_spec in extract_spec:
            field_name = field_spec.get("field", "")
            
            # Check for duplicate field names
            if field_name in field_names:
                errors.append(f"Duplicate extract field name: {field_name}")
            else:
                field_names.add(field_name)
            
            # Validate sub-extracts recursively
            if "sub_extracts" in field_spec and field_spec["sub_extracts"]:
                sub_errors = self._validate_extract_hierarchy(field_spec["sub_extracts"])
                errors.extend(sub_errors)
        
        return errors