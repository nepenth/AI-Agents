"""
Embedding generation service using AI backends for vector search.
"""

import asyncio
import logging
import hashlib
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.services.ai_service import get_ai_service
from app.ai.base import EmbeddingConfig, ModelType
from app.models.knowledge import KnowledgeItem, Embedding
from app.schemas.knowledge import EmbeddingCreate
from app.repositories.knowledge import get_knowledge_repository
from app.database.connection import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingChunk:
    """Represents a chunk of text for embedding generation."""
    text: str
    chunk_index: int
    token_count: int
    start_position: int
    end_position: int


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    embedding_id: str
    knowledge_item_id: str
    model: str
    chunk_index: int
    embedding_vector: List[float]
    chunk_text: str
    token_count: int
    embedding_dimension: int


class EmbeddingService:
    """Service for generating and managing embeddings for vector search."""
    
    def __init__(self):
        self.default_chunk_size = 512  # tokens
        self.chunk_overlap = 50  # tokens
        self.max_chunk_size = 1000  # tokens
        self.min_chunk_size = 50  # tokens
    
    async def generate_embeddings_for_knowledge_item(
        self,
        knowledge_item: KnowledgeItem,
        model_name: Optional[str] = None,
        force_regenerate: bool = False
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for a knowledge item.
        
        Args:
            knowledge_item: The knowledge item to generate embeddings for
            model_name: Optional specific model to use
            force_regenerate: Whether to regenerate existing embeddings
            
        Returns:
            List of embedding results
        """
        try:
            # Check if embeddings already exist
            if not force_regenerate and knowledge_item.has_embeddings:
                logger.info(f"Embeddings already exist for knowledge item {knowledge_item.id}")
                return []
            
            # Get AI service and available embedding models
            ai_service = get_ai_service()
            models = await ai_service.list_models()
            embedding_models = [m for m in models if m.get("type") == "text_generation"]
            
            if not embedding_models:
                raise ValueError("No embedding models available")
            
            # Use specified model or first available
            if model_name:
                model = next((m for m in embedding_models if m["name"] == model_name), None)
                if not model:
                    raise ValueError(f"Embedding model '{model_name}' not found")
            else:
                model = embedding_models[0]
                model_name = model["name"]
            
            logger.info(f"Generating embeddings for knowledge item {knowledge_item.id} using model {model_name}")
            
            # Chunk the content
            chunks = self._chunk_text(knowledge_item.enhanced_content)
            
            if not chunks:
                logger.warning(f"No chunks generated for knowledge item {knowledge_item.id}")
                return []
            
            # Generate embeddings for chunks
            embedding_results = []
            
            for chunk in chunks:
                try:
                    # Generate embedding
                    config = EmbeddingConfig(normalize=True, batch_size=1)
                    embeddings = await ai_service.generate_embeddings(
                        [chunk.text], model_name, config=config
                    )
                    
                    if not embeddings or not embeddings[0]:
                        logger.warning(f"Empty embedding generated for chunk {chunk.chunk_index}")
                        continue
                    
                    embedding_vector = embeddings[0]
                    
                    # Create embedding result
                    embedding_result = EmbeddingResult(
                        embedding_id=str(uuid.uuid4()),
                        knowledge_item_id=knowledge_item.id,
                        model=model_name,
                        chunk_index=chunk.chunk_index,
                        embedding_vector=embedding_vector,
                        chunk_text=chunk.text,
                        token_count=chunk.token_count,
                        embedding_dimension=len(embedding_vector)
                    )
                    
                    embedding_results.append(embedding_result)
                    
                except Exception as e:
                    logger.error(f"Failed to generate embedding for chunk {chunk.chunk_index}: {e}")
                    continue
            
            logger.info(f"Generated {len(embedding_results)} embeddings for knowledge item {knowledge_item.id}")
            return embedding_results
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for knowledge item {knowledge_item.id}: {e}")
            raise
    
    def _chunk_text(self, text: str) -> List[EmbeddingChunk]:
        """
        Chunk text into smaller pieces for embedding generation.
        
        Args:
            text: The text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or len(text.strip()) == 0:
            return []
        
        # Simple sentence-based chunking
        sentences = self._split_into_sentences(text)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        start_position = 0
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            
            # If adding this sentence would exceed chunk size, finalize current chunk
            if current_tokens + sentence_tokens > self.default_chunk_size and current_chunk:
                chunk = EmbeddingChunk(
                    text=current_chunk.strip(),
                    chunk_index=chunk_index,
                    token_count=current_tokens,
                    start_position=start_position,
                    end_position=start_position + len(current_chunk)
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, self.chunk_overlap)
                current_chunk = overlap_text + " " + sentence
                current_tokens = self._estimate_tokens(current_chunk)
                chunk_index += 1
                start_position += len(current_chunk) - len(overlap_text) - len(sentence) - 1
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_tokens += sentence_tokens
        
        # Add final chunk if it has content
        if current_chunk.strip() and current_tokens >= self.min_chunk_size:
            chunk = EmbeddingChunk(
                text=current_chunk.strip(),
                chunk_index=chunk_index,
                token_count=current_tokens,
                start_position=start_position,
                end_position=start_position + len(current_chunk)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        import re
        
        # Simple sentence splitting - could be improved with proper NLP
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Simple estimation: ~4 characters per token
        return max(1, len(text) // 4)
    
    def _get_overlap_text(self, text: str, overlap_tokens: int) -> str:
        """Get overlap text from the end of a chunk."""
        words = text.split()
        if len(words) <= overlap_tokens:
            return text
        
        overlap_words = words[-overlap_tokens:]
        return " ".join(overlap_words)
    
    async def save_embeddings(self, embedding_results: List[EmbeddingResult]) -> List[Embedding]:
        """
        Save embedding results to the database.
        
        Args:
            embedding_results: List of embedding results to save
            
        Returns:
            List of saved embedding objects
        """
        if not embedding_results:
            return []
        
        knowledge_repo = get_knowledge_repository()
        saved_embeddings = []
        
        async with get_db_session() as db:
            for result in embedding_results:
                try:
                    embedding_create = EmbeddingCreate(
                        id=result.embedding_id,
                        knowledge_item_id=result.knowledge_item_id,
                        model=result.model,
                        chunk_index=result.chunk_index,
                        chunk_text=result.chunk_text,
                        embedding_dimension=result.embedding_dimension,
                        token_count=result.token_count,
                        # Note: embedding vector would be stored in a separate vector column
                        # This would require pgvector integration
                    )
                    
                    embedding = await knowledge_repo.create_embedding(db, embedding_create)
                    saved_embeddings.append(embedding)
                    
                except Exception as e:
                    logger.error(f"Failed to save embedding {result.embedding_id}: {e}")
                    continue
        
        logger.info(f"Saved {len(saved_embeddings)} embeddings to database")
        return saved_embeddings
    
    async def batch_generate_embeddings(
        self,
        knowledge_items: List[KnowledgeItem],
        model_name: Optional[str] = None,
        batch_size: int = 5
    ) -> Dict[str, List[EmbeddingResult]]:
        """
        Generate embeddings for multiple knowledge items in batches.
        
        Args:
            knowledge_items: List of knowledge items
            model_name: Optional model name to use
            batch_size: Number of items to process concurrently
            
        Returns:
            Dictionary mapping knowledge item IDs to embedding results
        """
        results = {}
        
        # Process in batches to avoid overwhelming the AI service
        for i in range(0, len(knowledge_items), batch_size):
            batch = knowledge_items[i:i + batch_size]
            
            # Process batch concurrently
            batch_tasks = [
                self.generate_embeddings_for_knowledge_item(item, model_name)
                for item in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Collect results
            for j, result in enumerate(batch_results):
                item = batch[j]
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate embeddings for {item.id}: {result}")
                    results[item.id] = []
                else:
                    results[item.id] = result
            
            # Small delay between batches
            if i + batch_size < len(knowledge_items):
                await asyncio.sleep(1)
        
        return results
    
    async def update_embeddings_for_item(
        self,
        knowledge_item: KnowledgeItem,
        model_name: Optional[str] = None
    ) -> List[EmbeddingResult]:
        """
        Update embeddings for a knowledge item (regenerate if content changed).
        
        Args:
            knowledge_item: The knowledge item to update embeddings for
            model_name: Optional model name to use
            
        Returns:
            List of new embedding results
        """
        # Delete existing embeddings
        knowledge_repo = get_knowledge_repository()
        
        async with get_db_session() as db:
            await knowledge_repo.delete_embeddings_for_item(db, knowledge_item.id)
        
        # Generate new embeddings
        return await self.generate_embeddings_for_knowledge_item(
            knowledge_item, model_name, force_regenerate=True
        )
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()


# Global service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service