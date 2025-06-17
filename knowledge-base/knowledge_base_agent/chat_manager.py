"""
Chat Manager Module

This module handles the chat functionality, allowing users to query the
knowledge base.
"""

import logging
from typing import List, Dict, Any, Optional

from .config import Config
from .http_client import HTTPClient
from .embedding_manager import EmbeddingManager
from .prompts import LLMPrompts

class ChatManager:
    """Manages the chat functionality."""

    def __init__(self, config: Config, http_client: HTTPClient, embedding_manager: EmbeddingManager):
        self.config = config
        self.http_client = http_client
        self.embedding_manager = embedding_manager
        self.text_model = config.text_model
        self.chat_model = config.chat_model
        self.logger = logging.getLogger(__name__)

    async def handle_chat_query(self, query: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Handles a chat query by finding relevant documents and generating a response.
        """
        try:
            # 1. Find similar documents
            similar_docs = await self.embedding_manager.find_similar_documents(query, top_k=5)

            # 2. Prepare context from relevant documents
            if similar_docs:
                context_sections = []
                for doc in similar_docs:
                    doc_title = doc.get('title', 'Unknown')
                    doc_content = doc.get('content', '')
                    if doc_content:
                        context_sections.append(f"Source: {doc_title}\nContent: {doc_content}")
                
                context = "\n\n---\n\n".join(context_sections)
            else:
                context = "No relevant information found in the knowledge base."
            
            # 3. Construct the full user message with query and context
            system_prompt = LLMPrompts.get_chat_prompt()
            user_message = f"""Query: {query}

Relevant Knowledge Base Context:
{context}

Please answer the query based on the provided context from the knowledge base. If the context doesn't contain relevant information, state that the information is not available in the knowledge base."""

            # 4. Generate response using the LLM
            target_model = model or self.chat_model or self.text_model
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            response_text = await self.http_client.ollama_chat(
                model=target_model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more focused responses
                top_p=0.9
            )

            # 5. Format and return the response
            return {
                "response": response_text,
                "sources": [
                    {
                        "id": doc.get("id"),
                        "type": doc.get("type", "item"),
                        "title": doc.get("title", "Unknown"),
                        "score": doc.get("score", 0.0)
                    }
                    for doc in similar_docs[:3]  # Limit sources to top 3
                ]
            }
        except Exception as e:
            self.logger.error(f"Error handling chat query: {e}", exc_info=True)
            return {"error": "An error occurred while processing your query. Please try again."}