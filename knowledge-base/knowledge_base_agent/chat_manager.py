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

            # 2. Prepare context for the LLM
            context = "\n".join([f"Source: {doc['source']}\nContent: {doc['content']}" for doc in similar_docs])
            
            # 3. Generate response using the LLM
            prompt = LLMPrompts.get_chat_prompt()
            
            # Use the specified model, or the default chat model from config
            target_model = model or self.chat_model

            response_text = await self.http_client.ollama_chat(
                model=target_model,
                messages=[{"role": "user", "content": prompt}]
            )

            # 4. Format and return the response
            return {
                "response": response_text,
                "sources": [
                    {
                        "id": doc.get("doc_id"),
                        "type": doc.get("doc_type"),
                        "source": doc.get("source"),
                        "title": doc.get("title")
                    }
                    for doc in similar_docs
                ]
            }
        except Exception as e:
            logging.error(f"Error handling chat query: {e}", exc_info=True)
            return {"error": "An error occurred while processing your query."}

    async def _generate_llm_response(self, query: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a response from the LLM based on the query and documents."""
        
        system_prompt = LLMPrompts.get_chat_prompt()
        
        context_str = "\n\n---\n\n".join(
            [f"**Source: {doc['title']}**\n{doc['content']}" for doc in documents]
        )
        
        user_message = (
            f"**User Query:**\n{query}\n\n"
            f"**Relevant Documents from Knowledge Base:**\n{context_str}"
        )

        llm_response = await self.http_client.send_llm_request(
            model=self.config.chat_model or self.config.text_model,
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=0.2,
            max_tokens=1500
        )
        
        if not llm_response or not llm_response.get("success"):
            raise Exception("LLM request failed or returned empty content.")
            
        return llm_response