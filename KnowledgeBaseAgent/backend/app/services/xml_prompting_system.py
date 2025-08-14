"""
XML-Based Prompting System for structured AI interactions.
Provides comprehensive prompt templates with validation and versioning.
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)


class PromptType(str, Enum):
    """Types of XML prompts."""
    MEDIA_ANALYSIS = "media_analysis"
    CONTENT_UNDERSTANDING = "content_understanding"
    CATEGORIZATION = "categorization"
    SYNTHESIS_GENERATION = "synthesis_generation"
    EMBEDDING_OPTIMIZATION = "embedding_optimization"
    README_GENERATION = "readme_generation"


@dataclass
class PromptTemplate:
    """XML prompt template definition."""
    name: str
    prompt_type: PromptType
    version: str
    description: str
    template: str
    required_variables: List[str] = field(default_factory=list)
    optional_variables: List[str] = field(default_factory=list)
    output_schema: Optional[Dict[str, Any]] = None
    validation_rules: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PromptValidationResult:
    """Result of prompt validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    generated_prompt: Optional[str] = None


class XMLPromptingSystem:
    """Comprehensive XML-based prompting system."""
    
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Initialize default prompt templates."""
        # Media Analysis Template
        media_analysis_template = """
<task>
    <instruction>Analyze the {media_type} content and provide comprehensive understanding</instruction>
    <context>
        <tweet_text>{tweet_context}</tweet_text>
        <media_url>{media_url}</media_url>
        <media_type>{media_type}</media_type>
        <alt_text>{alt_text}</alt_text>
        <author>@{author_username}</author>
    </context>
    <output_format>
        <visual_description>Detailed description of what is shown in the media</visual_description>
        <key_elements>
            <element>Important visual elements, objects, people, text, etc.</element>
        </key_elements>
        <context_relevance>How the media relates to and supports the tweet text</context_relevance>
        <technical_details>Any technical information visible (code, diagrams, charts, etc.)</technical_details>
        <emotional_tone>The mood or emotional impact of the media</emotional_tone>
        <text_content>Any text visible in the media (OCR-style extraction)</text_content>
    </output_format>
    <requirements>
        <requirement>Provide detailed visual analysis</requirement>
        <requirement>Extract any visible text accurately</requirement>
        <requirement>Identify technical content if present</requirement>
        <requirement>Relate media to tweet context</requirement>
    </requirements>
</task>
        """.strip()
        
        self.register_template(PromptTemplate(
            name="media_analysis_v1",
            prompt_type=PromptType.MEDIA_ANALYSIS,
            version="1.0",
            description="Comprehensive media analysis for vision models",
            template=media_analysis_template,
            required_variables=["media_type", "tweet_context", "media_url", "author_username"],
            optional_variables=["alt_text"],
            output_schema={
                "visual_description": "string",
                "key_elements": "array",
                "context_relevance": "string",
                "technical_details": "string",
                "emotional_tone": "string",
                "text_content": "string"
            }
        ))
        
        # Content Understanding Template
        content_understanding_template = """
<task>
    <instruction>Generate collective understanding of this Twitter/X content combining text and media analysis</instruction>
    <context>
        <tweet_content>{tweet_content}</tweet_content>
        <author>@{author_username}</author>
        <engagement_metrics>
            <likes>{like_count}</likes>
            <retweets>{retweet_count}</retweets>
            <replies>{reply_count}</replies>
        </engagement_metrics>
        {media_analysis_section}
        {thread_context_section}
    </context>
    <output_format>
        <main_topic>Primary topic or theme of the content</main_topic>
        <key_insights>
            <insight>Important insights or takeaways</insight>
        </key_insights>
        <technical_details>Technical information, code, or domain-specific content</technical_details>
        <context_relevance>Why this content is valuable for knowledge base</context_relevance>
        <summary>Concise summary combining text and media understanding</summary>
        <knowledge_category>Suggested category for knowledge organization</knowledge_category>
    </output_format>
    <requirements>
        <requirement>Combine text and media analysis into unified understanding</requirement>
        <requirement>Identify technical or domain-specific content</requirement>
        <requirement>Provide actionable insights</requirement>
        <requirement>Suggest appropriate categorization</requirement>
    </requirements>
</task>
        """.strip()
        
        self.register_template(PromptTemplate(
            name="content_understanding_v1",
            prompt_type=PromptType.CONTENT_UNDERSTANDING,
            version="1.0",
            description="Collective understanding generation combining text and media",
            template=content_understanding_template,
            required_variables=["tweet_content", "author_username"],
            optional_variables=["like_count", "retweet_count", "reply_count", "media_analysis_section", "thread_context_section"],
            output_schema={
                "main_topic": "string",
                "key_insights": "array",
                "technical_details": "string",
                "context_relevance": "string",
                "summary": "string",
                "knowledge_category": "string"
            }
        ))
        
        # Categorization Template
        categorization_template = """
<task>
    <instruction>Categorize content with existing category intelligence and technical domain naming</instruction>
    <context>
        <content>{content}</content>
        <collective_understanding>{collective_understanding}</collective_understanding>
        <existing_categories>
            {existing_categories_list}
        </existing_categories>
        <category_guidelines>
            <guideline>Use short, technical domain names (e.g., "ml", "devops", "security")</guideline>
            <guideline>Prefer existing categories when content fits</guideline>
            <guideline>Create new categories only for distinct technical domains</guideline>
            <guideline>Use lowercase with hyphens for multi-word categories</guideline>
        </category_guidelines>
    </context>
    <output_format>
        <main_category>Primary technical domain category</main_category>
        <sub_category>More specific subcategory if applicable</sub_category>
        <confidence>Confidence level (0.0-1.0) in categorization</confidence>
        <reasoning>Explanation for category selection</reasoning>
        <alternative_categories>
            <category>Other possible categories considered</category>
        </alternative_categories>
        <new_category_justification>If creating new category, explain why existing ones don't fit</new_category_justification>
    </output_format>
    <requirements>
        <requirement>Use existing categories when possible</requirement>
        <requirement>Follow technical domain naming conventions</requirement>
        <requirement>Provide clear reasoning for categorization</requirement>
        <requirement>Justify new category creation</requirement>
    </requirements>
</task>
        """.strip()
        
        self.register_template(PromptTemplate(
            name="categorization_v1",
            prompt_type=PromptType.CATEGORIZATION,
            version="1.0",
            description="AI categorization with existing category intelligence",
            template=categorization_template,
            required_variables=["content", "collective_understanding"],
            optional_variables=["existing_categories_list"],
            output_schema={
                "main_category": "string",
                "sub_category": "string",
                "confidence": "number",
                "reasoning": "string",
                "alternative_categories": "array",
                "new_category_justification": "string"
            }
        ))
        
        # Synthesis Generation Template
        synthesis_template = """
<task>
    <instruction>Generate comprehensive technical synthesis from multiple sources</instruction>
    <context>
        <topic>{synthesis_topic}</topic>
        <source_count>{source_count}</source_count>
        <sources>
            {sources_content}
        </sources>
        <target_audience>{target_audience}</target_audience>
        <synthesis_type>{synthesis_type}</synthesis_type>
    </context>
    <output_format>
        <title>Comprehensive title for the synthesis document</title>
        <executive_summary>High-level overview of key findings and insights</executive_summary>
        <main_content>
            <section>
                <heading>Section title</heading>
                <content>Detailed analysis and synthesis</content>
            </section>
        </main_content>
        <key_takeaways>
            <takeaway>Important insights or conclusions</takeaway>
        </key_takeaways>
        <technical_details>Specific technical information, code examples, or implementation details</technical_details>
        <references>Source attribution and references</references>
        <related_topics>
            <topic>Related areas for further exploration</topic>
        </related_topics>
    </output_format>
    <requirements>
        <requirement>Synthesize information from all provided sources</requirement>
        <requirement>Maintain technical accuracy and depth</requirement>
        <requirement>Provide actionable insights and conclusions</requirement>
        <requirement>Structure content for target audience</requirement>
        <requirement>Include proper source attribution</requirement>
    </requirements>
</task>
        """.strip()
        
        self.register_template(PromptTemplate(
            name="synthesis_generation_v1",
            prompt_type=PromptType.SYNTHESIS_GENERATION,
            version="1.0",
            description="Technical synthesis generation from multiple sources",
            template=synthesis_template,
            required_variables=["synthesis_topic", "source_count", "sources_content"],
            optional_variables=["target_audience", "synthesis_type"],
            output_schema={
                "title": "string",
                "executive_summary": "string",
                "main_content": "array",
                "key_takeaways": "array",
                "technical_details": "string",
                "references": "string",
                "related_topics": "array"
            }
        ))
        
        # README Generation Template
        readme_template = """
<task>
    <instruction>Generate comprehensive README with navigation structure and technical documentation</instruction>
    <context>
        <knowledge_base_stats>
            <total_items>{total_items}</total_items>
            <categories>{categories_list}</categories>
            <recent_additions>{recent_count}</recent_additions>
        </knowledge_base_stats>
        <content_overview>
            {content_overview}
        </content_overview>
        <navigation_structure>
            {navigation_tree}
        </navigation_structure>
    </context>
    <output_format>
        <title>Knowledge Base title</title>
        <description>Overview of the knowledge base purpose and contents</description>
        <statistics>
            <stat>Key statistics about the knowledge base</stat>
        </statistics>
        <navigation>
            <section>
                <name>Section name</name>
                <description>Section description</description>
                <items>
                    <item>Navigation item with link</item>
                </items>
            </section>
        </navigation>
        <getting_started>Instructions for using the knowledge base</getting_started>
        <recent_updates>
            <update>Recent additions or changes</update>
        </recent_updates>
        <contributing>Guidelines for contributing to the knowledge base</contributing>
    </output_format>
    <requirements>
        <requirement>Create clear navigation structure</requirement>
        <requirement>Include relevant statistics</requirement>
        <requirement>Provide user-friendly getting started guide</requirement>
        <requirement>Highlight recent updates and changes</requirement>
        <requirement>Use markdown formatting for GitHub compatibility</requirement>
    </requirements>
</task>
        """.strip()
        
        self.register_template(PromptTemplate(
            name="readme_generation_v1",
            prompt_type=PromptType.README_GENERATION,
            version="1.0",
            description="README generation with navigation and documentation",
            template=readme_template,
            required_variables=["total_items", "categories_list", "content_overview"],
            optional_variables=["recent_count", "navigation_tree"],
            output_schema={
                "title": "string",
                "description": "string",
                "statistics": "array",
                "navigation": "array",
                "getting_started": "string",
                "recent_updates": "array",
                "contributing": "string"
            }
        ))
    
    def register_template(self, template: PromptTemplate):
        """Register a new prompt template."""
        template_key = f"{template.prompt_type}_{template.version}"
        self.templates[template_key] = template
        logger.info(f"Registered prompt template: {template_key}")
    
    def get_template(self, prompt_type: PromptType, version: str = "1.0") -> Optional[PromptTemplate]:
        """Get a prompt template by type and version."""
        template_key = f"{prompt_type}_{version}"
        return self.templates.get(template_key)
    
    def list_templates(self, prompt_type: Optional[PromptType] = None) -> List[PromptTemplate]:
        """List available templates, optionally filtered by type."""
        if prompt_type:
            return [t for t in self.templates.values() if t.prompt_type == prompt_type]
        return list(self.templates.values())
    
    def generate_prompt(self, prompt_type: PromptType, variables: Dict[str, Any], 
                       version: str = "1.0") -> PromptValidationResult:
        """Generate a prompt from template with variable substitution."""
        template = self.get_template(prompt_type, version)
        if not template:
            return PromptValidationResult(
                is_valid=False,
                errors=[f"Template not found: {prompt_type}_{version}"]
            )
        
        # Validate required variables
        validation_result = self._validate_variables(template, variables)
        if not validation_result.is_valid:
            return validation_result
        
        # Generate prompt with variable substitution
        try:
            generated_prompt = self._substitute_variables(template.template, variables)
            
            # Validate XML structure
            xml_validation = self._validate_xml_structure(generated_prompt)
            if not xml_validation.is_valid:
                return xml_validation
            
            # Apply validation rules
            rule_validation = self._apply_validation_rules(template, generated_prompt, variables)
            if not rule_validation.is_valid:
                return rule_validation
            
            return PromptValidationResult(
                is_valid=True,
                generated_prompt=generated_prompt
            )
            
        except Exception as e:
            logger.error(f"Error generating prompt: {e}")
            return PromptValidationResult(
                is_valid=False,
                errors=[f"Prompt generation failed: {str(e)}"]
            )
    
    def validate_output(self, prompt_type: PromptType, output: str, 
                       version: str = "1.0") -> PromptValidationResult:
        """Validate AI output against expected schema."""
        template = self.get_template(prompt_type, version)
        if not template or not template.output_schema:
            return PromptValidationResult(
                is_valid=True,
                warnings=["No output schema defined for validation"]
            )
        
        try:
            # Try to parse as XML first
            root = ET.fromstring(f"<root>{output}</root>")
            
            errors = []
            warnings = []
            
            # Check required fields from schema
            for field, field_type in template.output_schema.items():
                element = root.find(field)
                if element is None:
                    errors.append(f"Missing required field: {field}")
                elif field_type == "array" and element.text and not element.findall("*"):
                    warnings.append(f"Field '{field}' should contain sub-elements for array type")
            
            return PromptValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings
            )
            
        except ET.ParseError as e:
            # Try to validate as structured text
            return self._validate_text_output(template, output)
    
    def create_media_analysis_prompt(self, media_url: str, media_type: str, 
                                   tweet_context: str, author_username: str,
                                   alt_text: str = "") -> str:
        """Create media analysis prompt with proper variable substitution."""
        variables = {
            "media_url": media_url,
            "media_type": media_type,
            "tweet_context": tweet_context,
            "author_username": author_username,
            "alt_text": alt_text or "No alt text provided"
        }
        
        result = self.generate_prompt(PromptType.MEDIA_ANALYSIS, variables)
        if result.is_valid:
            return result.generated_prompt
        else:
            logger.error(f"Failed to generate media analysis prompt: {result.errors}")
            raise ValueError(f"Prompt generation failed: {result.errors}")
    
    def create_content_understanding_prompt(self, tweet_content: str, author_username: str,
                                          media_analysis: Optional[str] = None,
                                          thread_context: Optional[str] = None,
                                          engagement_metrics: Optional[Dict[str, int]] = None) -> str:
        """Create content understanding prompt."""
        variables = {
            "tweet_content": tweet_content,
            "author_username": author_username,
            "like_count": engagement_metrics.get("like_count", 0) if engagement_metrics else 0,
            "retweet_count": engagement_metrics.get("retweet_count", 0) if engagement_metrics else 0,
            "reply_count": engagement_metrics.get("reply_count", 0) if engagement_metrics else 0,
        }
        
        # Add optional sections
        if media_analysis:
            variables["media_analysis_section"] = f"<media_analysis>{media_analysis}</media_analysis>"
        else:
            variables["media_analysis_section"] = ""
            
        if thread_context:
            variables["thread_context_section"] = f"<thread_context>{thread_context}</thread_context>"
        else:
            variables["thread_context_section"] = ""
        
        result = self.generate_prompt(PromptType.CONTENT_UNDERSTANDING, variables)
        if result.is_valid:
            return result.generated_prompt
        else:
            logger.error(f"Failed to generate content understanding prompt: {result.errors}")
            raise ValueError(f"Prompt generation failed: {result.errors}")
    
    def create_categorization_prompt(self, content: str, collective_understanding: str,
                                   existing_categories: List[str] = None) -> str:
        """Create categorization prompt with existing category intelligence."""
        variables = {
            "content": content,
            "collective_understanding": collective_understanding,
        }
        
        if existing_categories:
            categories_xml = "\n".join([f"<category>{cat}</category>" for cat in existing_categories])
            variables["existing_categories_list"] = categories_xml
        else:
            variables["existing_categories_list"] = "<category>No existing categories</category>"
        
        result = self.generate_prompt(PromptType.CATEGORIZATION, variables)
        if result.is_valid:
            return result.generated_prompt
        else:
            logger.error(f"Failed to generate categorization prompt: {result.errors}")
            raise ValueError(f"Prompt generation failed: {result.errors}")
    
    def create_synthesis_prompt(self, topic: str, sources: List[Dict[str, Any]],
                              target_audience: str = "technical", 
                              synthesis_type: str = "comprehensive") -> str:
        """Create synthesis generation prompt."""
        sources_xml = ""
        for i, source in enumerate(sources, 1):
            sources_xml += f"""
<source id="{i}">
    <title>{source.get('title', 'Untitled')}</title>
    <content>{source.get('content', '')}</content>
    <author>{source.get('author', 'Unknown')}</author>
    <url>{source.get('url', '')}</url>
</source>"""
        
        variables = {
            "synthesis_topic": topic,
            "source_count": len(sources),
            "sources_content": sources_xml,
            "target_audience": target_audience,
            "synthesis_type": synthesis_type
        }
        
        result = self.generate_prompt(PromptType.SYNTHESIS_GENERATION, variables)
        if result.is_valid:
            return result.generated_prompt
        else:
            logger.error(f"Failed to generate synthesis prompt: {result.errors}")
            raise ValueError(f"Prompt generation failed: {result.errors}")
    
    def create_readme_prompt(self, total_items: int, categories: List[str],
                           content_overview: str, recent_count: int = 0,
                           navigation_tree: str = "") -> str:
        """Create README generation prompt."""
        categories_xml = "\n".join([f"<category>{cat}</category>" for cat in categories])
        
        variables = {
            "total_items": str(total_items),
            "categories_list": categories_xml,
            "content_overview": content_overview,
            "recent_count": str(recent_count),
            "navigation_tree": navigation_tree or "No navigation tree provided"
        }
        
        result = self.generate_prompt(PromptType.README_GENERATION, variables)
        if result.is_valid:
            return result.generated_prompt
        else:
            logger.error(f"Failed to generate README prompt: {result.errors}")
            raise ValueError(f"Prompt generation failed: {result.errors}")
    
    def _validate_variables(self, template: PromptTemplate, variables: Dict[str, Any]) -> PromptValidationResult:
        """Validate that all required variables are provided."""
        errors = []
        warnings = []
        
        # Check required variables
        for required_var in template.required_variables:
            if required_var not in variables:
                errors.append(f"Missing required variable: {required_var}")
            elif variables[required_var] is None:
                errors.append(f"Required variable '{required_var}' is None")
        
        # Check for unexpected variables
        all_expected = set(template.required_variables + template.optional_variables)
        for var in variables:
            if var not in all_expected:
                warnings.append(f"Unexpected variable: {var}")
        
        return PromptValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _substitute_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in template string."""
        result = template
        for var, value in variables.items():
            placeholder = f"{{{var}}}"
            result = result.replace(placeholder, str(value))
        
        # Check for unsubstituted placeholders
        remaining_placeholders = re.findall(r'\{([^}]+)\}', result)
        if remaining_placeholders:
            logger.warning(f"Unsubstituted placeholders: {remaining_placeholders}")
        
        return result
    
    def _validate_xml_structure(self, prompt: str) -> PromptValidationResult:
        """Validate XML structure of generated prompt."""
        try:
            ET.fromstring(prompt)
            return PromptValidationResult(is_valid=True)
        except ET.ParseError as e:
            return PromptValidationResult(
                is_valid=False,
                errors=[f"Invalid XML structure: {str(e)}"]
            )
    
    def _apply_validation_rules(self, template: PromptTemplate, prompt: str, 
                              variables: Dict[str, Any]) -> PromptValidationResult:
        """Apply custom validation rules to generated prompt."""
        errors = []
        warnings = []
        
        # Apply template-specific validation rules
        for rule in template.validation_rules:
            # This is a placeholder for custom rule implementation
            # In practice, you would implement specific validation logic here
            pass
        
        # General validation rules
        if len(prompt) < 100:
            warnings.append("Generated prompt is very short")
        
        if len(prompt) > 10000:
            warnings.append("Generated prompt is very long")
        
        return PromptValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_text_output(self, template: PromptTemplate, output: str) -> PromptValidationResult:
        """Validate output as structured text when XML parsing fails."""
        errors = []
        warnings = []
        
        if not template.output_schema:
            return PromptValidationResult(is_valid=True)
        
        # Check for presence of expected fields in text
        for field in template.output_schema.keys():
            if field.lower() not in output.lower():
                warnings.append(f"Expected field '{field}' not found in output")
        
        return PromptValidationResult(
            is_valid=True,  # Be lenient with text output
            warnings=warnings
        )


# Global instance
_xml_prompting_system: Optional[XMLPromptingSystem] = None


def get_xml_prompting_system() -> XMLPromptingSystem:
    """Get the global XML prompting system instance."""
    global _xml_prompting_system
    if _xml_prompting_system is None:
        _xml_prompting_system = XMLPromptingSystem()
    return _xml_prompting_system