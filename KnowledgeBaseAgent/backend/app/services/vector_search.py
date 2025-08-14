"""
Vector similarity search service using pgvector for semantic search.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.services.ai_service import get_ai_service
from app.services.embedding_service import get_embedding_service
from app.ai.base import EmbeddingConfig
from app.models.knowledge import KnowledgeItem, Embedding
from app.repositories.knowledge import get_knowledge_repository
from app.database.connection import get_db_session

logger = logging.getLogger(__name__)


class SearchType(str, Enum):
    """Types of search operations."""
    VECTOR_ONLY = "vector_only"
    TEXT_ONLY = "text_only"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """Result from vector search."""
    knowledge_item_id: str
    knowledge_item: Optional[KnowledgeItem]
    similarity_score: float
    chunk_text: str
    chunk_index: int
    embedding_id: str
    rank: int


@dataclass
class SearchQuery:
    """Search query configuration."""
    query_text: str
    search_type: SearchType = SearchType.HYBRID
    limit: int = 10
    similarity_threshold: float = 0.7
    categories: Optional[List[str]] = None
    model_name: Optional[str] = None
    include_content: bool = True


class VectorSearchService:
    """Service for performing vector similarity search."""
    
    def __init__(self):
        self.default_model = None
        self.similarity_threshold = 0.7
        self.max_results = 50
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        Perform semantic search using vector similarity.
        
        Args:
            query: Search query configuration
            
        Returns:
            List of search results ordered by relevance
        """
        try:
            if query.search_type == SearchType.TEXT_ONLY:
                return await self._text_search(query)
            elif query.search_type == SearchType.VECTOR_ONLY:
                return await self._vector_search(query)
            else:  # HYBRID
                return await self._hybrid_search(query)
                
        except Exception as e:
            logger.error(f"Search failed for query '{query.query_text}': {e}")
            raise
    
    async def _vector_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform vector similarity search."""
        # Generate embedding for query
        query_embedding = await self._generate_query_embedding(query.query_text, query.model_name)
        
        if not query_embedding:
            logger.warning("Failed to generate query embedding, falling back to text search")
            return await self._text_search(query)
        
        # Perform vector similarity search
        knowledge_repo = get_knowledge_repository()
        
        async with get_db_session() as db:
            # This would use pgvector for similarity search
            # For now, we'll simulate the search
            similar_embeddings = await self._simulate_vector_search(
                db, query_embedding, query.limit, query.similarity_threshold
            )
            
            # Convert to search results
            results = []
            for i, (embedding, similarity) in enumerate(similar_embeddings):
                knowledge_item = None
                if query.include_content:
                    knowledge_item = await knowledge_repo.get(db, embedding.knowledge_item_id)
                
                result = SearchResult(
                    knowledge_item_id=embedding.knowledge_item_id,
                    knowledge_item=knowledge_item,
                    similarity_score=similarity,
                    chunk_text=embedding.chunk_text,
                    chunk_index=embedding.chunk_index,
                    embedding_id=embedding.id,
                    rank=i + 1
                )
                results.append(result)
            
            # Filter by categories if specified
            if query.categories:
                results = await self._filter_by_categories(results, query.categories)
        
        return results
    
    async def _text_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform traditional text search."""
        knowledge_repo = get_knowledge_repository()
        
        async with get_db_session() as db:
            # This would use full-text search capabilities
            # For now, we'll simulate text search
            knowledge_items = await self._simulate_text_search(
                db, query.query_text, query.limit, query.categories
            )
            
            results = []
            for i, item in enumerate(knowledge_items):
                # Create a mock search result for text search
                result = SearchResult(
                    knowledge_item_id=item.id,
                    knowledge_item=item if query.include_content else None,
                    similarity_score=0.8,  # Mock similarity score
                    chunk_text=item.summary or item.enhanced_content[:200] + "...",
                    chunk_index=0,
                    embedding_id="",
                    rank=i + 1
                )
                results.append(result)
        
        return results
    
    async def _hybrid_search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform hybrid search combining vector and text search."""
        # Perform both searches
        vector_results = await self._vector_search(query)
        text_results = await self._text_search(query)
        
        # Combine and re-rank results
        combined_results = self._combine_search_results(vector_results, text_results, query.limit)
        
        return combined_results
    
    async def _generate_query_embedding(
        self, 
        query_text: str, 
        model_name: Optional[str] = None
    ) -> Optional[List[float]]:
        """Generate embedding for search query."""
        try:
            ai_service = get_ai_service()
            
            # Get available embedding models
            models = await ai_service.list_models()
            embedding_models = [m for m in models if m.get("type") == "text_generation"]
            
            if not embedding_models:
                logger.error("No embedding models available")
                return None
            
            # Use specified model or first available
            if model_name:
                model = next((m for m in embedding_models if m["name"] == model_name), None)
                if not model:
                    logger.warning(f"Model '{model_name}' not found, using default")
                    model_name = embedding_models[0]["name"]
            else:
                model_name = embedding_models[0]["name"]
            
            # Generate embedding
            config = EmbeddingConfig(normalize=True, batch_size=1)
            embeddings = await ai_service.generate_embeddings([query_text], model_name, config=config)
            
            if embeddings and embeddings[0]:
                return embeddings[0]
            else:
                logger.error("Failed to generate query embedding")
                return None
                
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            return None
    
    async def _simulate_vector_search(
        self,
        db,
        query_embedding: List[float],
        limit: int,
        threshold: float
    ) -> List[Tuple[Embedding, float]]:
        """
        Simulate vector similarity search.
        In production, this would use pgvector's similarity functions.
        """
        # This is a placeholder - in real implementation, this would be:
        # SELECT *, embedding <-> %s AS similarity 
        # FROM embeddings 
        # WHERE embedding <-> %s < %s 
        # ORDER BY similarity 
        # LIMIT %s
        
        # For now, return mock results
        mock_embeddings = []
        for i in range(min(limit, 5)):  # Mock 5 results
            embedding = Embedding(
                id=f"embedding_{i}",
                knowledge_item_id=f"knowledge_item_{i}",
                model="mock_model",
                chunk_index=0,
                chunk_text=f"Mock chunk text {i} related to the query",
                embedding_dimension=768,
                token_count=50
            )
            similarity = 0.9 - (i * 0.1)  # Decreasing similarity
            mock_embeddings.append((embedding, similarity))
        
        return mock_embeddings
    
    async def _simulate_text_search(
        self,
        db,
        query_text: str,
        limit: int,
        categories: Optional[List[str]] = None
    ) -> List[KnowledgeItem]:
        """
        Simulate text search.
        In production, this would use PostgreSQL full-text search.
        """
        # This is a placeholder - in real implementation, this would use:
        # SELECT *, ts_rank(to_tsvector(enhanced_content), plainto_tsquery(%s)) AS rank
        # FROM knowledge_items
        # WHERE to_tsvector(enhanced_content) @@ plainto_tsquery(%s)
        # ORDER BY rank DESC
        # LIMIT %s
        
        # For now, return mock results
        mock_items = []
        for i in range(min(limit, 3)):  # Mock 3 results
            item = KnowledgeItem(
                id=f"knowledge_item_{i}",
                content_item_id=f"content_item_{i}",
                display_title=f"Mock Knowledge Item {i}",
                summary=f"Mock summary {i} containing query terms",
                enhanced_content=f"Mock enhanced content {i} with detailed information about the query topic",
                key_points=[f"Key point {i}.1", f"Key point {i}.2"],
                entities=[],
                quality_score=0.8,
                completeness_score=0.7
            )
            mock_items.append(item)
        
        return mock_items
    
    def _combine_search_results(
        self,
        vector_results: List[SearchResult],
        text_results: List[SearchResult],
        limit: int
    ) -> List[SearchResult]:
        """Combine and re-rank vector and text search results."""
        # Create a map to avoid duplicates
        results_map = {}
        
        # Add vector results with higher weight
        for result in vector_results:
            key = result.knowledge_item_id
            if key not in results_map:
                # Boost vector similarity scores
                boosted_score = min(1.0, result.similarity_score * 1.2)
                result.similarity_score = boosted_score
                results_map[key] = result
        
        # Add text results with lower weight
        for result in text_results:
            key = result.knowledge_item_id
            if key not in results_map:
                # Reduce text search scores slightly
                reduced_score = result.similarity_score * 0.9
                result.similarity_score = reduced_score
                results_map[key] = result
            else:
                # Boost existing result if found in both searches
                existing = results_map[key]
                existing.similarity_score = min(1.0, existing.similarity_score * 1.1)
        
        # Sort by similarity score and limit results
        combined_results = list(results_map.values())
        combined_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Update ranks
        for i, result in enumerate(combined_results[:limit]):
            result.rank = i + 1
        
        return combined_results[:limit]
    
    async def _filter_by_categories(
        self,
        results: List[SearchResult],
        categories: List[str]
    ) -> List[SearchResult]:
        """Filter search results by categories."""
        if not categories:
            return results
        
        filtered_results = []
        
        for result in results:
            if result.knowledge_item:
                # Check if knowledge item's content item has matching categories
                # This would require loading the content item
                # For now, we'll keep all results
                filtered_results.append(result)
        
        return filtered_results
    
    async def find_similar_items(
        self,
        knowledge_item_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.8
    ) -> List[SearchResult]:
        """
        Find items similar to a given knowledge item.
        
        Args:
            knowledge_item_id: ID of the knowledge item to find similar items for
            limit: Maximum number of results
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            List of similar items
        """
        try:
            knowledge_repo = get_knowledge_repository()
            
            async with get_db_session() as db:
                # Get the knowledge item
                knowledge_item = await knowledge_repo.get(db, knowledge_item_id)
                if not knowledge_item:
                    raise ValueError(f"Knowledge item {knowledge_item_id} not found")
                
                # Use the item's content as query
                query = SearchQuery(
                    query_text=knowledge_item.enhanced_content[:500],  # Use first 500 chars
                    search_type=SearchType.VECTOR_ONLY,
                    limit=limit + 1,  # +1 to account for the item itself
                    similarity_threshold=similarity_threshold
                )
                
                results = await self._vector_search(query)
                
                # Remove the original item from results
                filtered_results = [r for r in results if r.knowledge_item_id != knowledge_item_id]
                
                return filtered_results[:limit]
                
        except Exception as e:
            logger.error(f"Failed to find similar items for {knowledge_item_id}: {e}")
            raise
    
    async def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            partial_query: Partial search query
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested queries
        """
        try:
            # This would typically use a search suggestion index
            # For now, return mock suggestions
            suggestions = [
                f"{partial_query} tutorial",
                f"{partial_query} guide",
                f"{partial_query} best practices",
                f"{partial_query} examples",
                f"{partial_query} documentation"
            ]
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get search suggestions for '{partial_query}': {e}")
            return []
    
    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search system statistics."""
        try:
            knowledge_repo = get_knowledge_repository()
            
            async with get_db_session() as db:
                # This would get actual statistics from the database
                # For now, return mock stats
                stats = {
                    "total_knowledge_items": 100,  # Mock count
                    "total_embeddings": 500,  # Mock count
                    "embedding_models": ["mock_model_1", "mock_model_2"],
                    "average_similarity_threshold": 0.75,
                    "search_performance_ms": 45
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {}


# Global service instance
_vector_search_service: Optional[VectorSearchService] = None


def get_vector_search_service() -> VectorSearchService:
    """Get the global vector search service instance."""
    global _vector_search_service
    if _vector_search_service is None:
        _vector_search_service = VectorSearchService()
    return _vector_search_service