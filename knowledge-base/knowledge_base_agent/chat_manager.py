"""
Enhanced Chat Manager Module

This module handles the chat functionality with modern AI agent design patterns,
providing expert-level technical guidance through optimized prompts, intelligent
context preparation, and query-type specialization.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
import time

from .config import Config
from .http_client import HTTPClient
from .embedding_manager import EmbeddingManager
from .json_prompt_manager import JsonPromptManager
from .response_formatter import get_response_formatter

class ChatManager:
    """
    Enhanced Chat Manager with modern AI agent design patterns.
    
    Features:
    - Query type detection and specialized prompts
    - Intelligent context preparation with relevance scoring
    - Enhanced search with increased document retrieval
    - Smart content truncation preserving technical details
    - Clear source attribution with document type indicators
    """

    def __init__(self, config: Config, http_client: HTTPClient, embedding_manager: EmbeddingManager):
        self.config = config
        self.http_client = http_client
        self.embedding_manager = embedding_manager
        self.text_model = config.text_model
        self.chat_model = config.chat_model
        self.logger = logging.getLogger(__name__)
        
        # Initialize JSON prompt manager for improved prompts
        try:
            self.json_prompt_manager = JsonPromptManager(config)
            self.logger.info("Initialized enhanced JSON prompt manager")
        except Exception as e:
            self.logger.warning(f"Failed to initialize JSON prompt manager: {e}")
            self.json_prompt_manager = None
        
        # Initialize response formatter for better output formatting
        try:
            self.response_formatter = get_response_formatter()
            self.logger.info("Initialized response formatter for enhanced output")
        except Exception as e:
            self.logger.warning(f"Failed to initialize response formatter: {e}")
            self.response_formatter = None

    def _detect_query_type(self, query: str) -> str:
        """
        Enhanced query type detection for specialized prompt selection.
        
        Returns: "implementation", "comparison", "conceptual", or "general"
        """
        query_lower = query.lower()
        
        # Implementation queries - how to do something
        implementation_keywords = [
            'how to', 'how do i', 'implement', 'setup', 'configure', 'install',
            'create', 'build', 'deploy', 'run', 'execute', 'start', 'launch',
            'tutorial', 'guide', 'step by step', 'walkthrough'
        ]
        
        if any(keyword in query_lower for keyword in implementation_keywords):
            return 'implementation'
        
        # Comparison queries - comparing options
        comparison_keywords = [
            'vs', 'versus', 'compare', 'comparison', 'difference', 'differences',
            'better', 'best', 'choose', 'choice', 'which', 'should i use',
            'pros and cons', 'advantages', 'disadvantages', 'trade-offs'
        ]
        
        if any(keyword in query_lower for keyword in comparison_keywords):
            return 'comparison'
        
        # Conceptual queries - understanding concepts
        conceptual_keywords = [
            'what is', 'what are', 'explain', 'definition', 'concept', 'theory',
            'understand', 'meaning', 'overview', 'introduction', 'basics',
            'fundamentals', 'principles', 'architecture', 'design pattern'
        ]
        
        if any(keyword in query_lower for keyword in conceptual_keywords):
            return 'conceptual'
        
        # Default to general
        return 'general'

    def _get_specialized_prompt(self, query_type: str) -> str:
        """Get specialized prompt based on query type."""
        if not self.json_prompt_manager:
            # Fallback to basic prompt if JSON manager not available
            return self._get_fallback_prompt()
        
        # Try to use the enhanced formatting prompt first
        try:
            enhanced_prompt_file = self.json_prompt_manager.prompts_dir / 'improved' / 'chat_enhanced_formatting.json'
            if enhanced_prompt_file.exists():
                import json
                with open(enhanced_prompt_file, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)
                    self.logger.info("Using enhanced formatting prompt for better AI responses")
                    return prompt_data['template']['content']
        except Exception as e:
            self.logger.warning(f"Failed to load enhanced formatting prompt: {e}")
        
        # Fallback to query-specific prompts
        prompt_map = {
            'implementation': 'chat_implementation_query',
            'comparison': 'chat_comparison_query',
            'conceptual': 'chat_conceptual_query',
            'general': 'chat_optimized_system'
        }
        
        prompt_id = prompt_map.get(query_type, 'chat_optimized_system')
        
        try:
            # Try to load from improved prompts first
            prompt_file = self.json_prompt_manager.prompts_dir / 'improved' / f'{prompt_id}.json'
            if prompt_file.exists():
                import json
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)
                    return prompt_data['template']['content']
            
            # Fallback to standard prompts
            return self.json_prompt_manager.render_prompt(prompt_id, {}, "standard").content
            
        except Exception as e:
            self.logger.warning(f"Failed to load specialized prompt {prompt_id}: {e}")
            return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if JSON prompts are not available."""
        return """You are a Senior Technical Expert with deep expertise in software engineering, system design, DevOps, and modern technology implementation. You provide expert guidance based on the user's personal knowledge base.

**Core Principles:**
• Base all responses strictly on the provided knowledge base context
• Provide technically accurate, implementation-focused advice
• Use clear source attribution: [📄 Title] for KB items, [📋 Title] for synthesis docs
• Connect related concepts and suggest exploration paths
• State clearly when information isn't available in the knowledge base

**Response Structure:**
1. **Direct Answer**: Address the specific question immediately
2. **Technical Details**: Implementation specifics, code examples, configurations
3. **Context & Trade-offs**: Why this approach, alternatives, considerations
4. **Sources**: Clear citations with document titles
5. **Next Steps**: Related topics or follow-up actions

Provide expert technical assistance based on the knowledge base context below."""

    def _intelligent_truncate(self, content: str, max_length: int, query: str) -> str:
        """Intelligently truncate content while preserving important sections."""
        
        if len(content) <= max_length:
            return content
        
        # Try to preserve sections most relevant to the query
        query_terms = set(query.lower().split())
        
        # Split into paragraphs
        paragraphs = content.split('\n\n')
        
        # Score paragraphs by relevance to query
        scored_paragraphs = []
        for i, para in enumerate(paragraphs):
            para_words = set(para.lower().split())
            relevance_score = len(query_terms.intersection(para_words))
            
            # Boost score for code blocks and technical sections
            if '```' in para or 'def ' in para or 'class ' in para or 'function' in para:
                relevance_score += 3
            if any(term in para.lower() for term in ['example', 'implementation', 'usage', 'configuration']):
                relevance_score += 2
            if any(term in para.lower() for term in ['install', 'setup', 'deploy', 'run']):
                relevance_score += 2
                
            scored_paragraphs.append((relevance_score, i, para))
        
        # Sort by relevance, keeping original order for equal scores
        scored_paragraphs.sort(key=lambda x: (-x[0], x[1]))
        
        # Build truncated content
        selected_content = []
        current_length = 0
        
        # Always include first paragraph (usually introduction)
        if paragraphs:
            selected_content.append(paragraphs[0])
            current_length += len(paragraphs[0])
        
        # Add most relevant paragraphs
        for score, idx, para in scored_paragraphs[1:]:
            if current_length + len(para) + 150 < max_length:  # Leave room for truncation notice
                selected_content.append(para)
                current_length += len(para)
            else:
                break
        
        # Add truncation notice if content was truncated
        if len(selected_content) < len(paragraphs):
            selected_content.append("\n[... additional technical details available in full document ...]")
        
        return '\n\n'.join(selected_content)

    def _prepare_enhanced_context(self, similar_docs: List[Dict[str, Any]], query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Enhanced context preparation with intelligent summarization and relevance scoring.
        Returns tuple of (formatted_context, enhanced_sources)
        """
        if not similar_docs:
            return "No relevant documents found in knowledge base.", []
        
        # Separate by relevance score for different treatment
        high_relevance = [doc for doc in similar_docs if doc.get('score', 0) > 0.8]
        medium_relevance = [doc for doc in similar_docs if 0.6 <= doc.get('score', 0) <= 0.8]
        low_relevance = [doc for doc in similar_docs if doc.get('score', 0) < 0.6]
        
        context_sections = []
        enhanced_sources = []
        
        # High relevance: Full content with intelligent truncation
        for doc in high_relevance[:3]:
            content = doc.get('content', '')
            title = doc.get('title', 'Untitled')
            doc_type = doc.get('type', 'unknown')
            score = doc.get('score', 0)
            category = doc.get('category', doc.get('main_category', 'Unknown'))
            subcategory = doc.get('subcategory', doc.get('sub_category', 'Unknown'))
            
            # Apply intelligent truncation for long content
            max_length = 2500 if doc_type == 'synthesis' else 2000  # Increased limits
            if len(content) > max_length:
                content = self._intelligent_truncate(content, max_length, query)
            
            # Format with clear attribution
            doc_marker = "📄" if doc_type == 'kb_item' else "📋"
            context_sections.append(
                f"**{doc_marker} {title}** (Relevance: {score:.3f})\n"
                f"Category: {category}/{subcategory}\n{content}"
            )
            
            enhanced_sources.append({
                'title': title,
                'type': doc_type,
                'score': score,
                'category': category,
                'subcategory': subcategory,
                'content_length': len(content),
                'doc_type_display': f"{doc_marker} {doc_type.replace('_', ' ').title()}"
            })
        
        # Medium relevance: Key points extraction
        for doc in medium_relevance[:4]:
            content = doc.get('content', '')
            title = doc.get('title', 'Untitled')
            doc_type = doc.get('type', 'unknown')
            score = doc.get('score', 0)
            category = doc.get('category', doc.get('main_category', 'Unknown'))
            
            # Extract key technical points relevant to query
            key_points = self._extract_key_points(content, query)
            
            doc_marker = "📄" if doc_type == 'kb_item' else "📋"
            context_sections.append(
                f"**{doc_marker} {title}** (Relevance: {score:.3f})\n"
                f"**Key Points:**\n{key_points}"
            )
            
            enhanced_sources.append({
                'title': title,
                'type': doc_type,
                'score': score,
                'category': category,
                'content_type': 'key_points',
                'doc_type_display': f"{doc_marker} {doc_type.replace('_', ' ').title()}"
            })
        
        # Low relevance: Brief mentions only if space allows
        if len(context_sections) < 6:
            for doc in low_relevance[:2]:
                title = doc.get('title', 'Untitled')
                doc_type = doc.get('type', 'unknown')
                score = doc.get('score', 0)
                
                # Just title and brief description
                brief_desc = self._extract_brief_description(doc.get('content', ''))
                doc_marker = "📄" if doc_type == 'kb_item' else "📋"
                
                context_sections.append(
                    f"**{doc_marker} {title}** (Relevance: {score:.3f})\n{brief_desc}"
                )
                
                enhanced_sources.append({
                    'title': title,
                    'type': doc_type,
                    'score': score,
                    'content_type': 'brief',
                    'doc_type_display': f"{doc_marker} {doc_type.replace('_', ' ').title()}"
                })
        
        # Combine all sections with clear separators
        full_context = "\n\n" + "="*50 + "\n\n".join(context_sections) + "\n\n" + "="*50
        
        return full_context, enhanced_sources

    def _extract_key_points(self, content: str, query: str) -> str:
        """Extract key technical points relevant to the query."""
        
        key_points = []
        
        # Extract code blocks
        code_blocks = re.findall(r'```[\s\S]*?```', content)
        if code_blocks:
            key_points.append(f"• Code examples: {len(code_blocks)} code blocks with implementation details")
        
        # Extract bullet points and numbered lists
        bullet_points = re.findall(r'^[•\-\*]\s+(.+)$', content, re.MULTILINE)
        numbered_points = re.findall(r'^\d+\.\s+(.+)$', content, re.MULTILINE)
        
        all_points = bullet_points + numbered_points
        
        # Filter points relevant to query
        query_terms = set(query.lower().split())
        relevant_points = []
        
        for point in all_points[:15]:  # Limit to first 15 points
            point_words = set(point.lower().split())
            if query_terms.intersection(point_words) or len(point) > 50:  # Include substantial points
                truncated_point = point[:120] + '...' if len(point) > 120 else point
                relevant_points.append(f"• {truncated_point}")
        
        if relevant_points:
            key_points.extend(relevant_points[:6])  # Top 6 relevant points
        
        # Extract technical terms and concepts
        tech_terms = self._extract_technical_terms(content)
        if tech_terms:
            key_points.append(f"• Technical concepts: {', '.join(tech_terms[:10])}")
        
        # Extract section headers
        headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
        if headers:
            key_points.append(f"• Sections covered: {', '.join(headers[:5])}")
        
        return '\n'.join(key_points) if key_points else "Key technical information available in full document."

    def _extract_brief_description(self, content: str) -> str:
        """Extract a brief description from content."""
        
        if not content:
            return "No content available."
        
        # Try to get first paragraph or first 250 characters
        first_para = content.split('\n\n')[0] if content else ""
        
        if len(first_para) > 250:
            # Find a good breaking point
            truncated = first_para[:250]
            last_space = truncated.rfind(' ')
            if last_space > 200:
                truncated = truncated[:last_space]
            return truncated + "..."
        
        return first_para

    def _extract_technical_terms(self, content: str) -> List[str]:
        """Extract technical terms and concepts from content."""
        
        # Common technical term patterns
        patterns = [
            r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase (React, JavaScript)
            r'\b[a-z]+(?:_[a-z]+)+\b',           # snake_case (user_id, api_key)
            r'\b[A-Z]{2,}\b',                    # ACRONYMS (API, HTTP, SQL)
            r'\b\w+\.\w+\b',                     # module.function (React.Component)
        ]
        
        technical_terms = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            technical_terms.update(matches)
        
        # Filter out common non-technical words
        common_words = {
            'The', 'This', 'That', 'With', 'From', 'When', 'Where', 'What', 'How',
            'And', 'But', 'For', 'Not', 'You', 'All', 'Can', 'Had', 'Her', 'Was',
            'One', 'Our', 'Out', 'Day', 'Get', 'Has', 'Him', 'His', 'Its',
            'New', 'Now', 'Old', 'See', 'Two', 'Way', 'Who', 'Boy', 'Did', 'Man',
            'May', 'Say', 'She', 'Use', 'Her', 'Each', 'Which', 'Their', 'Time',
            'Will', 'About', 'If', 'Up', 'Out', 'Many', 'Then', 'Them', 'These',
            'So', 'Some', 'Would', 'Make', 'Like', 'Into', 'Him', 'Has', 'More'
        }
        
        technical_terms = technical_terms - common_words
        
        return sorted(list(technical_terms))[:15]  # Return top 15 terms

    async def handle_chat_query(
        self,
        query: str,
        model: Optional[str] = None,
        use_knowledge_base: bool = True,
        search_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Enhanced chat query handler with modern AI agent design patterns.
        
        Features:
        - Query type detection and specialized prompts
        - Enhanced document retrieval (increased from 8 to 12)
        - Intelligent context preparation with relevance scoring
        - Performance metrics and comprehensive response metadata
        """
        try:
            # 1. Enhanced query type detection
            query_type = self._detect_query_type(query)
            self.logger.info(f"Detected query type: {query_type} for query: '{query[:50]}...'")

            similar_docs = []
            if use_knowledge_base:
                # 2. Enhanced document retrieval with increased top_k
                similar_docs = await self.embedding_manager.find_similar_documents(
                    query,
                    top_k=12,  # Increased from 8 to 12 for better coverage
                    include_scores=True
                )
            
            # 2b. Merge any client-provided search_context (from UI pre-search) into similar_docs
            #     so the assistant can leverage those hints alongside embeddings.
            if search_context:
                formatted_context: List[Dict[str, Any]] = []
                for src in search_context:
                    src_type = src.get('type')
                    # Normalize type names
                    if src_type in ('kb', 'kb_item'):
                        norm_type = 'kb_item'
                    elif src_type == 'synthesis':
                        norm_type = 'synthesis'
                    else:
                        norm_type = src_type or 'unknown'
                    formatted_context.append({
                        'title': src.get('title', 'Untitled'),
                        'score': float(src.get('score', 0.78)),  # reasonable default score
                        'content': src.get('content', ''),
                        'type': norm_type,
                        'id': src.get('id'),
                        'category': src.get('main_category') or src.get('category', ''),
                        'subcategory': src.get('sub_category') or src.get('subcategory', ''),
                    })
                # Deduplicate by (type, id), preferring earlier (UI-provided) items
                combined: List[Dict[str, Any]] = []
                seen: set = set()
                for doc in (formatted_context + (similar_docs or [])):
                    key = f"{doc.get('type')}:{doc.get('id')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    combined.append(doc)
                similar_docs = combined
            
            self.logger.info(f"Retrieved {len(similar_docs)} similar documents")

            # 3. Enhanced context preparation with intelligent summarization
            context, enhanced_sources = self._prepare_enhanced_context(similar_docs, query)
            
            # 4. Get specialized prompt based on query type
            system_prompt = self._get_specialized_prompt(query_type)
            
            # 5. Construct enhanced user message with clear structure
            user_message = f"""**USER QUERY:** {query}

**KNOWLEDGE BASE CONTEXT:**
{context}

**QUERY TYPE:** {query_type.upper()}

**INSTRUCTIONS:**
- Provide expert-level technical guidance based strictly on the knowledge base context
- Use clear source attribution: [📄 Title] for KB items, [📋 Title] for synthesis docs
- Structure your response according to the {query_type} query type guidelines
- Include specific implementation details, code examples, and configurations when available
- Suggest related topics and next steps for deeper exploration
- If information is missing from the knowledge base, clearly state this limitation

Please provide your comprehensive technical response."""

            # 6. Generate response with optimized parameters (using backend-aware model selection)
            target_model = model or self.config.get_model_for_backend('chat') or self.config.get_model_for_backend('text')
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            # Track performance metrics
            start_time = time.time()
            
            response_text = await self.http_client.chat(
                model=target_model,
                messages=messages,
                temperature=0.1,  # Lower temperature for more consistent, technical responses
                top_p=0.9,
                timeout=self.config.chat_timeout  # Use configurable chat timeout
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Format the response for better readability
            if self.response_formatter:
                try:
                    formatted_response = self.response_formatter.format_response(
                        response_text, 
                        context={'query_type': query_type, 'model': target_model}
                    )
                    self.logger.info("Applied response formatting for improved readability")
                    response_text = formatted_response
                except Exception as e:
                    self.logger.warning(f"Failed to format response: {e}")
                    # Continue with unformatted response
            
            # Calculate more accurate token counts using improved estimation
            # Based on OpenAI's rule of thumb: ~4 characters per token for English text
            # We'll be more conservative and use 3.5 characters per token
            def estimate_tokens(text: str) -> int:
                """Estimate token count using character-based method with adjustments for code/technical content."""
                if not text:
                    return 0
                
                # Count characters, excluding whitespace
                char_count = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))
                
                # Base estimation: 3.5 chars per token for technical content
                base_tokens = char_count / 3.5
                
                # Adjust for special content
                # Code blocks and technical terms tend to have more tokens
                if '```' in text or 'def ' in text or 'class ' in text:
                    base_tokens *= 1.2  # 20% more tokens for code
                
                # URLs and technical identifiers are often single tokens despite length
                import re
                url_count = len(re.findall(r'http[s]?://\S+', text))
                if url_count > 0:
                    base_tokens *= 0.9  # Slightly fewer tokens due to URL compression
                
                return int(base_tokens)
            
            # Calculate system prompt tokens
            system_prompt_tokens = estimate_tokens(system_prompt)
            
            # Calculate user message tokens (including context)
            user_message_tokens = estimate_tokens(user_message)
            
            # Calculate response tokens
            output_tokens = estimate_tokens(response_text)
            
            # Total input tokens
            input_tokens = system_prompt_tokens + user_message_tokens
            total_tokens = input_tokens + output_tokens
            
            # Calculate tokens per second (based on output generation)
            tokens_per_second = output_tokens / response_time if response_time > 0 else 0

            # 7. Format and return enhanced response
            return {
                "response": response_text,
                "query_type": query_type,
                "context_stats": {
                    "total_sources": len(enhanced_sources),
                    "synthesis_docs": sum(1 for s in enhanced_sources if s['type'] == 'synthesis'),
                    "kb_items": sum(1 for s in enhanced_sources if s['type'] == 'kb_item'),
                    "categories_covered": len(set(s['category'] for s in enhanced_sources if s.get('category')))
                },
                "sources": enhanced_sources[:5],  # Limit displayed sources but keep full metadata
                "model_used": target_model,
                "performance_metrics": {
                    "response_time_ms": round(response_time * 1000, 2),
                    "response_time_seconds": round(response_time, 2),
                    "estimated_input_tokens": round(input_tokens),
                    "estimated_output_tokens": round(output_tokens),
                    "estimated_total_tokens": round(total_tokens),
                    "tokens_per_second": round(tokens_per_second, 1),
                    "model": target_model,
                    "context_length": len(enhanced_sources)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error handling chat query: {e}", exc_info=True)
            return {
                "error": "An error occurred while processing your query. Please try again."
            }

    async def get_available_models(self) -> List[Dict[str, str]]:
        """Get list of available chat models from config and Ollama API."""
        models = []
        
        # First, add models from the backend-specific AVAILABLE_CHAT_MODELS config
        available_models = self.config.get_available_chat_models_for_backend()
        if available_models:
            for model_id in available_models:
                models.append({"id": model_id, "name": f"Chat Model ({model_id})"})
            self.logger.info(f"Added {len(available_models)} models from {self.config.inference_backend} backend config")
        
        # Add currently configured models if not already present (using backend-aware selection)
        configured_models = []
        chat_model = self.config.get_model_for_backend('chat')
        text_model = self.config.get_model_for_backend('text')
        
        if chat_model:
            configured_models.append({"id": chat_model, "name": f"Default Chat Model ({chat_model})"})
        if text_model and text_model != chat_model:
            configured_models.append({"id": text_model, "name": f"Text Model ({text_model})"})

        for model in configured_models:
            if model['id'] not in [m['id'] for m in models]:
                models.insert(0, model)
        
        # Try to get additional models from the configured backend (optional)
        try:
            backend_models = await self.http_client.get_available_models()
            
            # Add any additional models from the backend that aren't already in our list
            for model in backend_models:
                if model['id'] not in [m['id'] for m in models]:
                    models.append(model)
                    
        except Exception as e:
            self.logger.warning(f"Could not fetch models from {self.config.inference_backend} backend: {e}")
        
        # Ensure we have at least one model
        if not models:
            models = [{"id": "default", "name": "Default Model"}]
            
        self.logger.info(f"Returning {len(models)} available models")
        return models