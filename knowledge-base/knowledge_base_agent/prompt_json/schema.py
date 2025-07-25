"""
JSON Schema definitions for the prompt system.

This module contains the comprehensive JSON schema that defines the structure
and validation rules for JSON prompt configurations.
"""

# JSON Schema for prompt configurations
PROMPT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "Unique identifier for the prompt"
        },
        "name": {
            "type": "string", 
            "description": "Human-readable name for the prompt"
        },
        "version": {
            "type": "string",
            "description": "Version of the prompt configuration"
        },
        "task": {
            "type": "string",
            "description": "The primary task this prompt performs"
        },
        "topic": {
            "type": "string",
            "description": "The subject matter or domain of the prompt"
        },
        "category": {
            "type": "string",
            "description": "Category for organizing prompts"
        },
        "model_type": {
            "enum": ["standard", "reasoning", "both"],
            "description": "Compatible model types"
        },
        "text": {
            "type": "string",
            "description": "The prompt template text with parameter placeholders"
        },
        "format": {
            "type": "string",
            "description": "Format type of the prompt (instruction, conversation, etc.)"
        },
        "input": {
            "type": "object",
            "properties": {
                "parameters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "required": {"type": "boolean"},
                            "description": {"type": "string"},
                            "validation": {"type": "object"},
                            "default_value": {}
                        },
                        "required": ["name", "type", "required", "description"]
                    }
                }
            },
            "required": ["parameters"]
        },
        "output": {
            "type": "object",
            "properties": {
                "format": {
                    "enum": ["json", "text", "markdown", "structured"]
                },
                "schema": {"type": "object"},
                "max_words": {"type": "integer"},
                "extract": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "sub_extracts": {
                                "type": "array",
                                "items": {"$ref": "#/properties/output/properties/extract/items"}
                            }
                        },
                        "required": ["field", "type", "description"]
                    }
                }
            },
            "required": ["format"]
        },
        "constraints": {
            "type": "object",
            "properties": {
                "max_length": {"type": "integer"},
                "min_length": {"type": "integer"},
                "timeout": {"type": "integer"},
                "temperature": {"type": "number"}
            }
        },
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "condition": {"type": "string"},
                    "modifications": {"type": "object"}
                },
                "required": ["name", "condition", "modifications"]
            }
        },
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "input": {"type": "object"},
                    "expected_output": {"type": "object"},
                    "description": {"type": "string"}
                },
                "required": ["input", "expected_output"]
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "created": {"type": "string"},
                "updated": {"type": "string"},
                "author": {"type": "string"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "performance_metrics": {"type": "object"}
            }
        }
    },
    "required": ["id", "name", "task", "text", "format", "input", "output"]
}

# Schema for reasoning model message format
REASONING_MESSAGE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "role": {
            "enum": ["system", "user", "assistant"]
        },
        "content": {
            "type": "string"
        }
    },
    "required": ["role", "content"]
}

# Schema for prompt collections/categories
PROMPT_COLLECTION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "collection_id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "version": {"type": "string"},
        "prompts": {
            "type": "array",
            "items": {"$ref": "#/definitions/prompt"},
            "definitions": {
                "prompt": PROMPT_SCHEMA
            }
        }
    },
    "required": ["collection_id", "name", "prompts"]
}