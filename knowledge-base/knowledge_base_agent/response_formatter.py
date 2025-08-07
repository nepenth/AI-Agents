"""
Response Formatter Module

This module provides post-processing for AI responses to improve formatting,
readability, and structure. It cleans up common formatting issues and
enhances the presentation of technical content.
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class FormattingRule:
    """Represents a formatting rule with pattern and replacement."""
    name: str
    pattern: str
    replacement: str
    description: str
    flags: int = re.MULTILINE


class ResponseFormatter:
    """
    Enhanced response formatter for AI chat responses.
    
    Features:
    - Cleans up common AI formatting issues
    - Improves markdown structure
    - Enhances code block formatting
    - Standardizes source attribution
    - Improves typography and spacing
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.formatting_rules = self._initialize_formatting_rules()
        
    def _initialize_formatting_rules(self) -> List[FormattingRule]:
        """Initialize the formatting rules for response cleanup."""
        return [
            # Remove excessive separators
            FormattingRule(
                name="remove_excessive_separators",
                pattern=r'^-{3,}\s*$',
                replacement='',
                description="Remove standalone separator lines"
            ),
            
            # Fix header formatting
            FormattingRule(
                name="fix_bold_headers",
                pattern=r'^\s*\*\*([^*]+)\*\*\s*$',
                replacement=r'## \1',
                description="Convert standalone bold text to headers"
            ),
            
            # Fix emoji headers
            FormattingRule(
                name="fix_emoji_headers",
                pattern=r'^\s*(✅|❗|🔍|📌|🚀|💡|⚠️|🎯)\s*\*\*([^*]+)\*\*\s*',
                replacement=r'### \1 \2\n',
                description="Convert emoji + bold to proper headers"
            ),
            
            # Fix source references
            FormattingRule(
                name="fix_source_references",
                pattern=r'\[📄\s*([^\]]+)\]',
                replacement=r'[📄 \1]',
                description="Standardize KB item references"
            ),
            
            FormattingRule(
                name="fix_synthesis_references",
                pattern=r'\[📋\s*([^\]]+)\]',
                replacement=r'[📋 \1]',
                description="Standardize synthesis document references"
            ),
            
            # Improve list formatting
            FormattingRule(
                name="fix_bullet_points",
                pattern=r'^\s*[-*]\s+',
                replacement='• ',
                description="Standardize bullet points"
            ),
            
            # Fix excessive line breaks
            FormattingRule(
                name="fix_excessive_breaks",
                pattern=r'\n{4,}',
                replacement='\n\n\n',
                description="Limit excessive line breaks"
            ),
            
            # Fix code block language tags
            FormattingRule(
                name="fix_code_blocks",
                pattern=r'```(\w+)?\n([\s\S]*?)```',
                replacement=self._fix_code_block,
                description="Improve code block formatting"
            ),
            
            # Fix table formatting
            FormattingRule(
                name="fix_table_spacing",
                pattern=r'\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|',
                replacement=r'| \1 | \2 | \3 |',
                description="Improve table cell spacing"
            ),
            
            # Remove trailing whitespace
            FormattingRule(
                name="remove_trailing_whitespace",
                pattern=r'[ \t]+$',
                replacement='',
                description="Remove trailing whitespace"
            ),
        ]
    
    def _fix_code_block(self, match) -> str:
        """Fix code block formatting with proper language detection."""
        lang = match.group(1) or ''
        code = match.group(2).strip()
        
        # Detect language if not specified
        if not lang:
            lang = self._detect_code_language(code)
        
        # Ensure proper spacing
        return f'```{lang}\n{code}\n```'
    
    def _detect_code_language(self, code: str) -> str:
        """Detect programming language from code content."""
        code_lower = code.lower()
        
        # JavaScript/TypeScript patterns
        if any(keyword in code_lower for keyword in ['function', 'const ', 'let ', 'var ', '=>', 'async']):
            if 'interface' in code_lower or 'type ' in code_lower:
                return 'typescript'
            return 'javascript'
        
        # Python patterns
        if any(keyword in code_lower for keyword in ['def ', 'import ', 'from ', 'class ', 'if __name__']):
            return 'python'
        
        # Bash/Shell patterns
        if any(keyword in code_lower for keyword in ['#!/bin/bash', 'echo ', 'cd ', 'ls ', 'mkdir', 'chmod']):
            return 'bash'
        
        # SQL patterns
        if any(keyword in code_lower for keyword in ['select ', 'from ', 'where ', 'insert ', 'update ', 'delete ']):
            return 'sql'
        
        # CSS patterns
        if any(keyword in code_lower for keyword in ['{', '}', 'color:', 'background:', 'margin:', 'padding:']):
            return 'css'
        
        # HTML patterns
        if any(keyword in code_lower for keyword in ['<html', '<div', '<span', '<p>', '<h1', '<a ']):
            return 'html'
        
        # YAML patterns
        if any(keyword in code_lower for keyword in ['apiversion:', 'kind:', 'metadata:', 'spec:']):
            return 'yaml'
        
        # JSON patterns
        if code.strip().startswith('{') and code.strip().endswith('}'):
            return 'json'
        
        return 'text'
    
    def format_response(self, response_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Format and clean up an AI response for better readability.
        
        Args:
            response_text: The raw AI response text
            context: Optional context information for formatting decisions
            
        Returns:
            Formatted and cleaned response text
        """
        if not response_text:
            return response_text
        
        try:
            formatted_text = response_text
            
            # Apply formatting rules
            for rule in self.formatting_rules:
                try:
                    if callable(rule.replacement):
                        # Handle callable replacements (like code block fixing)
                        formatted_text = re.sub(
                            rule.pattern, 
                            rule.replacement, 
                            formatted_text, 
                            flags=rule.flags
                        )
                    else:
                        formatted_text = re.sub(
                            rule.pattern, 
                            rule.replacement, 
                            formatted_text, 
                            flags=rule.flags
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to apply formatting rule '{rule.name}': {e}")
                    continue
            
            # Post-processing improvements
            formatted_text = self._improve_structure(formatted_text)
            formatted_text = self._enhance_readability(formatted_text)
            
            return formatted_text.strip()
            
        except Exception as e:
            self.logger.error(f"Error formatting response: {e}")
            return response_text  # Return original on error
    
    def _improve_structure(self, text: str) -> str:
        """Improve overall document structure."""
        
        # Ensure proper spacing around headers
        text = re.sub(r'\n(#{1,6}\s+[^\n]+)\n', r'\n\n\1\n\n', text)
        
        # Ensure proper spacing around code blocks
        text = re.sub(r'\n(```[\s\S]*?```)\n', r'\n\n\1\n\n', text)
        
        # Ensure proper spacing around tables
        text = re.sub(r'\n(\|[^\n]+\|)\n', r'\n\n\1\n', text)
        
        # Fix multiple consecutive headers
        text = re.sub(r'\n(#{1,6}\s+[^\n]+)\n\n(#{1,6}\s+[^\n]+)\n', r'\n\1\n\2\n', text)
        
        return text
    
    def _enhance_readability(self, text: str) -> str:
        """Enhance text readability with better formatting."""
        
        # Improve list spacing
        text = re.sub(r'\n(• [^\n]+)\n(• [^\n]+)', r'\n\1\n\2', text)
        
        # Improve paragraph breaks
        text = re.sub(r'([.!?])\s*\n([A-Z])', r'\1\n\n\2', text)
        
        # Fix spacing around blockquotes
        text = re.sub(r'\n(>[^\n]+)\n', r'\n\n\1\n\n', text)
        
        # Ensure consistent spacing
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    def extract_sources(self, text: str) -> Tuple[str, List[str]]:
        """
        Extract source references from formatted text.
        
        Returns:
            Tuple of (text_without_sources, list_of_sources)
        """
        sources = []
        
        # Find all source references
        kb_sources = re.findall(r'\[📄 ([^\]]+)\]', text)
        synthesis_sources = re.findall(r'\[📋 ([^\]]+)\]', text)
        
        sources.extend([f"📄 {source}" for source in kb_sources])
        sources.extend([f"📋 {source}" for source in synthesis_sources])
        
        # Remove duplicates while preserving order
        unique_sources = []
        seen = set()
        for source in sources:
            if source not in seen:
                unique_sources.append(source)
                seen.add(source)
        
        return text, unique_sources
    
    def format_for_display(self, response_text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format response for display with enhanced metadata.
        
        Args:
            response_text: The AI response text
            metadata: Optional metadata about the response
            
        Returns:
            Dictionary with formatted response and display metadata
        """
        # Format the response
        formatted_text = self.format_response(response_text)
        
        # Extract sources
        text_without_sources, sources = self.extract_sources(formatted_text)
        
        # Calculate readability metrics
        readability_score = self._calculate_readability_score(formatted_text)
        
        # Detect content structure
        structure = self._analyze_content_structure(formatted_text)
        
        return {
            'formatted_text': formatted_text,
            'text_without_sources': text_without_sources,
            'extracted_sources': sources,
            'readability_score': readability_score,
            'content_structure': structure,
            'formatting_applied': True,
            'word_count': len(formatted_text.split()),
            'estimated_reading_time': self._estimate_reading_time(formatted_text)
        }
    
    def _calculate_readability_score(self, text: str) -> float:
        """Calculate a simple readability score (0-100)."""
        if not text:
            return 0.0
        
        # Simple metrics
        sentences = len(re.findall(r'[.!?]+', text))
        words = len(text.split())
        
        if sentences == 0:
            return 50.0  # Neutral score for no sentences
        
        avg_words_per_sentence = words / sentences
        
        # Score based on average sentence length (optimal: 15-20 words)
        if 15 <= avg_words_per_sentence <= 20:
            score = 100.0
        elif avg_words_per_sentence < 15:
            score = 80.0 + (avg_words_per_sentence / 15) * 20
        else:
            score = max(20.0, 100.0 - (avg_words_per_sentence - 20) * 2)
        
        return min(100.0, max(0.0, score))
    
    def _analyze_content_structure(self, text: str) -> Dict[str, Any]:
        """Analyze the structure of the formatted content."""
        structure = {
            'has_headers': bool(re.search(r'^#{1,6}\s+', text, re.MULTILINE)),
            'has_code_blocks': bool(re.search(r'```[\s\S]*?```', text)),
            'has_lists': bool(re.search(r'^\s*[•\-\*]\s+', text, re.MULTILINE)),
            'has_tables': bool(re.search(r'\|[^\n]+\|', text)),
            'has_links': bool(re.search(r'\[([^\]]+)\]\(([^)]+)\)', text)),
            'has_sources': bool(re.search(r'\[📄|📋[^\]]+\]', text)),
            'header_count': len(re.findall(r'^#{1,6}\s+', text, re.MULTILINE)),
            'code_block_count': len(re.findall(r'```[\s\S]*?```', text)),
            'list_item_count': len(re.findall(r'^\s*[•\-\*]\s+', text, re.MULTILINE)),
            'paragraph_count': len([p for p in text.split('\n\n') if p.strip()])
        }
        
        return structure
    
    def _estimate_reading_time(self, text: str) -> int:
        """Estimate reading time in seconds (average 200 words per minute)."""
        word_count = len(text.split())
        reading_time_minutes = word_count / 200  # 200 WPM average
        return int(reading_time_minutes * 60)  # Convert to seconds


# Global formatter instance
_formatter_instance = None


def get_response_formatter() -> ResponseFormatter:
    """Get the global response formatter instance."""
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = ResponseFormatter()
    return _formatter_instance


def format_ai_response(response_text: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function to format an AI response.
    
    Args:
        response_text: The raw AI response text
        context: Optional context for formatting decisions
        
    Returns:
        Formatted response text
    """
    formatter = get_response_formatter()
    return formatter.format_response(response_text, context)