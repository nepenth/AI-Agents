"""
Chat Manager Module

This module handles the chat functionality, allowing users to query the
knowledge base with enhanced technical expertise and comprehensive responses.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import time

from .config import Config
from .http_client import HTTPClient
from .embedding_manager import EmbeddingManager
from .prompts import LLMPrompts

class ChatManager:
    """Manages the enhanced chat functionality with technical expertise and comprehensive responses."""

    def __init__(self, config: Config, http_client: HTTPClient, embedding_manager: EmbeddingManager):
        self.config = config
        self.http_client = http_client
        self.embedding_manager = embedding_manager
        self.text_model = config.text_model
        self.chat_model = config.chat_model
        self.logger = logging.getLogger(__name__)

    def _classify_query_type(self, query: str) -> str:
        """
        Classify the type of query to use appropriate response prompts.
        Returns: "explanation", "implementation", "comparison", "troubleshooting", "architecture", or "general"
        """
        query_lower = query.lower()
        
        # Implementation-focused queries
        if any(word in query_lower for word in ['how to', 'implement', 'setup', 'configure', 'install', 'deploy', 'build']):
            return "implementation"
        
        # Comparison queries
        elif any(word in query_lower for word in ['vs', 'versus', 'compare', 'difference', 'better', 'best', 'choose']):
            return "comparison"
        
        # Troubleshooting queries
        elif any(word in query_lower for word in ['error', 'problem', 'issue', 'debug', 'fix', 'broken', 'not working', 'troubleshoot']):
            return "troubleshooting"
        
        # Architecture/design queries
        elif any(word in query_lower for word in ['architecture', 'design', 'pattern', 'scalability', 'performance', 'system']):
            return "architecture"
        
        # Explanation queries
        elif any(word in query_lower for word in ['what is', 'explain', 'define', 'meaning', 'concept', 'understand']):
            return "explanation"
        
        return "general"

    def _prepare_enhanced_context(self, similar_docs: List[Dict[str, Any]], query: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Prepare enhanced context from similar documents with rich metadata and structure.
        Returns tuple of (formatted_context, enhanced_sources)
        """
        if not similar_docs:
            return "No relevant information found in the knowledge base.", []

        # Separate documents by type
        synthesis_docs = []
        kb_item_docs = []
        
        for doc in similar_docs:
            doc_type = doc.get('type', 'item')
            if doc_type == 'synthesis':
                synthesis_docs.append(doc)
            else:
                kb_item_docs.append(doc)

        context_sections = []
        enhanced_sources = []

        # Process synthesis documents first (higher-level insights)
        if synthesis_docs:
            context_sections.append("## 📋 SYNTHESIS DOCUMENTS (Strategic Insights & Patterns)")
            for doc in synthesis_docs:
                title = doc.get('title', 'Unknown Synthesis')
                content = doc.get('content', '')
                category = doc.get('main_category', 'Unknown')
                subcategory = doc.get('sub_category', 'Unknown')
                score = doc.get('score', 0.0)
                
                context_sections.append(
                    f"### 📋 {category}/{subcategory} Synthesis: {title}\n"
                    f"**Relevance Score**: {score:.3f}\n"
                    f"**Content**: {content[:1500]}{'...' if len(content) > 1500 else ''}\n"
                )
                
                enhanced_sources.append({
                    "id": doc.get("id"),
                    "type": "synthesis",
                    "title": title,
                    "category": category,
                    "subcategory": subcategory,
                    "score": score,
                    "doc_type_display": "📋 Synthesis",
                    "url": f"/synthesis/{doc.get('id')}" if doc.get('id') else None
                })

        # Process individual knowledge base items
        if kb_item_docs:
            context_sections.append("## 📄 KNOWLEDGE BASE ITEMS (Detailed Implementation & Examples)")
            for doc in kb_item_docs:
                title = doc.get('title', 'Unknown Item')
                content = doc.get('content', '')
                category = doc.get('main_category', 'Unknown')
                subcategory = doc.get('sub_category', 'Unknown') 
                score = doc.get('score', 0.0)
                
                context_sections.append(
                    f"### 📄 {category}/{subcategory}: {title}\n"
                    f"**Relevance Score**: {score:.3f}\n"
                    f"**Content**: {content[:1200]}{'...' if len(content) > 1200 else ''}\n"
                )
                
                enhanced_sources.append({
                    "id": doc.get("id"),
                    "type": "item",
                    "title": title,
                    "category": category,
                    "subcategory": subcategory,
                    "score": score,
                    "doc_type_display": "📄 KB Item",
                    "url": f"/item/{doc.get('id')}" if doc.get('id') else None
                })

        # Add query context and cross-reference suggestions
        context_sections.append(
            f"\n## 🎯 QUERY CONTEXT\n"
            f"**User Query**: {query}\n"
            f"**Available Sources**: {len(synthesis_docs)} synthesis documents, {len(kb_item_docs)} knowledge base items\n"
            f"**Coverage**: Strategic insights from synthesis documents + detailed implementations from KB items\n"
        )

        formatted_context = "\n\n".join(context_sections)
        return formatted_context, enhanced_sources

    async def handle_chat_query(self, query: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Handles a chat query with enhanced technical expertise and comprehensive responses.
        """
        try:
            # 1. Classify query type for appropriate response strategy
            query_type = self._classify_query_type(query)
            self.logger.debug(f"Classified query type: {query_type}")

            # 2. Find similar documents with improved retrieval
            similar_docs = await self.embedding_manager.find_similar_documents(
                query, 
                top_k=8  # Increased for better coverage
            )

            # 3. Prepare enhanced context with rich metadata
            context, enhanced_sources = self._prepare_enhanced_context(similar_docs, query)
            
            # 4. Select appropriate system prompt based on context and query type
            if any(source['type'] == 'synthesis' for source in enhanced_sources):
                system_prompt = LLMPrompts.get_synthesis_aware_chat_prompt()
            else:
                system_prompt = LLMPrompts.get_chat_prompt()
            
            # Add query-specific guidance
            query_specific_prompt = LLMPrompts.get_contextual_chat_response_prompt(query_type)
            
            # 5. Construct enhanced user message
            user_message = f"""{query_specific_prompt}

**User Query**: {query}

**Available Knowledge Base Context**:
{context}

**Response Instructions**:
- Provide a comprehensive, expert-level response based on the available context
- Use the enhanced citation system as specified in your system prompt
- Include cross-references to related topics when relevant
- Structure your response according to the query type guidelines
- If applicable, suggest logical next steps or deeper exploration paths
- Be specific about which sources support each part of your response

Please provide your expert analysis and guidance based on the available knowledge base context."""

            # 6. Generate response using the LLM
            target_model = model or self.chat_model or self.text_model
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            # Track performance metrics
            start_time = time.time()
            
            response_text = await self.http_client.ollama_chat(
                model=target_model,
                messages=messages,
                temperature=0.2,  # Lower temperature for more focused, technical responses
                top_p=0.9
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
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
                    "kb_items": sum(1 for s in enhanced_sources if s['type'] == 'item'),
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
        """Get list of available chat models."""
        try:
            # This would typically call the Ollama API to get available models
            # For now, return configured models
            models = []
            if self.chat_model:
                models.append({"id": self.chat_model, "name": f"Chat Model ({self.chat_model})"})
            if self.text_model and self.text_model != self.chat_model:
                models.append({"id": self.text_model, "name": f"Text Model ({self.text_model})"})
            
            # Add some common model options if none configured
            if not models:
                models = [
                    {"id": "llama2", "name": "Llama 2"},
                    {"id": "codellama", "name": "Code Llama"},
                    {"id": "mistral", "name": "Mistral"}
                ]
            
            return models
        except Exception as e:
            self.logger.error(f"Error getting available models: {e}")
            return [{"id": "default", "name": "Default Model"}]