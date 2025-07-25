"""
Base classes and interfaces for the JSON prompt system.

This module defines the core abstractions and interfaces that all JSON prompt
components must implement, ensuring consistency and extensibility.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class ModelType(Enum):
    """Supported model types for prompt generation."""
    STANDARD = "standard"
    REASONING = "reasoning"
    BOTH = "both"


class OutputFormat(Enum):
    """Supported output formats for prompts."""
    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"
    STRUCTURED = "structured"


@dataclass
class ParameterSpec:
    """Specification for a prompt input parameter."""
    name: str
    type: str
    required: bool
    description: str
    validation: Optional[Dict[str, Any]] = None
    default_value: Optional[Any] = None


@dataclass
class ExtractField:
    """Specification for extracting structured data from prompt output."""
    field: str
    type: str
    description: str
    sub_extracts: List['ExtractField'] = None
    
    def __post_init__(self):
        if self.sub_extracts is None:
            self.sub_extracts = []


@dataclass
class OutputSpec:
    """Specification for prompt output format and structure."""
    format: OutputFormat
    schema: Optional[Dict[str, Any]] = None
    max_words: Optional[int] = None
    extract_fields: List[ExtractField] = None
    
    def __post_init__(self):
        if self.extract_fields is None:
            self.extract_fields = []


@dataclass
class VariantSpec:
    """Specification for prompt variants based on conditions."""
    name: str
    condition: str
    modifications: Dict[str, Any]


@dataclass
class ExampleSpec:
    """Specification for prompt examples."""
    input: Dict[str, Any]
    expected_output: Dict[str, Any]
    description: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation operations."""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class PromptResult:
    """Result of prompt execution."""
    rendered_prompt: str
    parameters_used: Dict[str, Any]
    model_type: ModelType
    execution_time: Optional[float] = None
    validation_result: Optional[ValidationResult] = None


class PromptRenderer(ABC):
    """Abstract base class for prompt rendering."""
    
    @abstractmethod
    def render(self, template: str, parameters: Dict[str, Any]) -> str:
        """Render a prompt template with the given parameters."""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any], spec: List[ParameterSpec]) -> ValidationResult:
        """Validate parameters against their specifications."""
        pass


class PromptValidator(ABC):
    """Abstract base class for prompt validation."""
    
    @abstractmethod
    def validate_schema(self, prompt_config: Dict[str, Any]) -> ValidationResult:
        """Validate a prompt configuration against the JSON schema."""
        pass
    
    @abstractmethod
    def validate_output(self, output: Any, output_spec: OutputSpec) -> ValidationResult:
        """Validate prompt output against the expected format."""
        pass


class PromptLoader(ABC):
    """Abstract base class for loading prompt configurations."""
    
    @abstractmethod
    def load_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """Load a prompt configuration by ID."""
        pass
    
    @abstractmethod
    def load_all_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Load all available prompt configurations."""
        pass


class PromptExecutor(ABC):
    """Abstract base class for executing prompts."""
    
    @abstractmethod
    def execute(self, prompt_id: str, parameters: Dict[str, Any]) -> PromptResult:
        """Execute a prompt with the given parameters."""
        pass
    
    @abstractmethod
    def get_variants(self, prompt_id: str) -> List[str]:
        """Get available variants for a prompt."""
        pass