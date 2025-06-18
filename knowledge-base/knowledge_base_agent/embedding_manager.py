"""
Embedding Manager Module

This module is responsible for generating, storing, and retrieving embeddings
for knowledge base items and synthesis documents.
"""

import logging
import asyncio
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text

from .config import Config
from .http_client import HTTPClient
from .models import db, KnowledgeBaseItem, SubcategorySynthesis, Embedding
from .custom_types import Synthesis
from .file_utils import async_json_load, async_write_text
from .exceptions import AIError

class EmbeddingManager:
    """Manages the creation and storage of embeddings."""

    def __init__(self, config: Config, http_client: HTTPClient):
        self.config = config
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
        self.embedding_model = config.embedding_model

    async def generate_all_embeddings(
        self,
        force_regenerate: bool = False,
        phase_emitter_func=None
    ) -> Tuple[int, int]:
        """
        Generate embeddings for all KB items and synthesis documents.
        Returns the number of processed items and the number of errors.
        """
        self.logger.info("Starting embedding generation for all documents.")
        
        items_to_process = []
        
        # Get all KB items
        kb_items = KnowledgeBaseItem.query.all()
        for item in kb_items:
            items_to_process.append({'type': 'kb_item', 'id': item.id, 'content': item.content, 'title': item.title})
            
        # Get all synthesis documents
        syntheses = SubcategorySynthesis.query.all()
        for synth in syntheses:
            items_to_process.append({'type': 'synthesis', 'id': synth.id, 'content': synth.synthesis_content, 'title': synth.synthesis_title})

        total_items = len(items_to_process)
        self.logger.info(f"Found {total_items} documents to process for embeddings.")

        if phase_emitter_func:
            phase_emitter_func(
                "embedding_generation",
                "in_progress",
                f"Generating embeddings for {total_items} documents.",
                is_sub_step_update=False,
                processed_count=0,
                total_count=total_items,
                error_count=0
            )

        processed_count = 0
        error_count = 0

        for i, item_data in enumerate(items_to_process):
            try:
                # Skip items with empty or None content
                if not item_data.get('content') or not item_data['content'].strip():
                    self.logger.info(f"Skipping {item_data['type']} {item_data['id']} - empty content")
                    processed_count += 1
                    continue

                if not force_regenerate:
                    existing_embedding = Embedding.query.filter_by(
                        document_id=item_data['id'],
                        document_type=item_data['type'],
                        model=self.embedding_model
                    ).first()
                    if existing_embedding:
                        self.logger.debug(f"Skipping existing embedding for {item_data['type']} {item_data['id']}")
                        processed_count += 1
                        continue

                embedding_vector = await self._generate_embedding(item_data['content'])
                
                await self._save_embedding(
                    document_id=item_data['id'],
                    document_type=item_data['type'],
                    embedding_vector=embedding_vector,
                    model=self.embedding_model
                )
                
                self.logger.debug(f"Generated and saved embedding for {item_data['type']} {item_data['id']}")

                processed_count += 1
                
                if phase_emitter_func:
                    phase_emitter_func(
                        "embedding_generation",
                        f"Processing item {i+1}/{total_items}",
                        "in_progress",
                        is_sub_step_update=True,
                        processed_count=processed_count,
                        total_count=total_items,
                        error_count=error_count
                    )
            except Exception as e:
                self.logger.error(f"Error generating embedding for {item_data['type']} {item_data['id']}: {e}", exc_info=True)
                error_count += 1

        self.logger.info(f"Embedding generation finished. Processed: {processed_count}, Errors: {error_count}")
        
        # Emit completion phase update
        if phase_emitter_func:
            if error_count > 0:
                phase_emitter_func(
                    "embedding_generation",
                    "completed_with_errors",
                    f"Embedding generation completed with {error_count} errors. Processed: {processed_count}/{total_items}",
                    is_sub_step_update=False,
                    processed_count=processed_count,
                    total_count=total_items,
                    error_count=error_count
                )
            else:
                phase_emitter_func(
                    "embedding_generation",
                    "completed",
                    f"Successfully generated embeddings for {processed_count} documents.",
                    is_sub_step_update=False,
                    processed_count=processed_count,
                    total_count=total_items,
                    error_count=error_count
                )
        
        return processed_count, error_count

    async def _generate_embedding(self, content: str) -> List[float]:
        """Generate embedding for a given text content."""
        
        try:
            # Validate content before sending to API
            if content is None:
                raise ValueError("Content is None - cannot generate embedding")
            
            if not isinstance(content, str):
                raise ValueError(f"Content must be a string, got {type(content)}: {content}")
            
            if not content.strip():
                raise ValueError(f"Content is empty or whitespace-only: '{content}'")
            
            content_length = len(content)
            content_preview = content[:100] + "..." if len(content) > 100 else content
            self.logger.debug(f"Generating embedding for content (length={content_length}): {content_preview}")
            
            # Use the direct ollama_embed method instead of the non-existent send_embedding_request
            embedding = await self.http_client.ollama_embed(
                model=self.embedding_model,
                prompt=content
            )
            
            if not embedding or len(embedding) == 0:
                raise ValueError(f"Received empty embedding from API for content: {content_preview}")
            
            self.logger.debug(f"Successfully generated embedding with dimension {len(embedding)}")
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding for content (length={len(content) if content else 0}): {e}")
            self.logger.error(f"Content preview: '{content[:200] if content else 'None'}...'")
            raise Exception(f"Failed to generate embedding from API: {e}")

    async def _save_embedding(self, document_id: int, document_type: str, embedding_vector: List[float], model: str):
        """Save an embedding to the database."""
        
        existing_embedding = Embedding.query.filter_by(
            document_id=document_id,
            document_type=document_type,
            model=model
        ).first()

        embedding_bytes = np.array(embedding_vector).astype(np.float32).tobytes()

        if existing_embedding:
            existing_embedding.embedding = embedding_bytes
            existing_embedding.created_at = datetime.now(timezone.utc)
        else:
            new_embedding = Embedding(
                document_id=document_id,
                document_type=document_type,
                embedding=embedding_bytes,
                model=model,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_embedding)
        
        db.session.commit()

    async def find_similar_documents(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find similar documents to a query using embeddings."""
        self.logger.info(f"Searching for documents similar to: '{query}'")

        query_embedding = await self._generate_embedding(query)
        
        all_embeddings = Embedding.query.filter_by(model=self.embedding_model).all()
        
        if not all_embeddings:
            return []

        # Convert stored byte embeddings back to numpy arrays
        doc_embeddings = np.array([np.frombuffer(e.embedding, dtype=np.float32) for e in all_embeddings])
        query_embedding_np = np.array(query_embedding).astype(np.float32)

        # Calculate cosine similarity
        similarities = self._cosine_similarity(query_embedding_np, doc_embeddings)
        
        # Get top k results
        top_k_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for i in top_k_indices:
            embedding_record = all_embeddings[i]
            document = self._get_document_by_embedding(embedding_record)
            if document:
                results.append({
                    "title": document.title if hasattr(document, 'title') else document.synthesis_title,
                    "score": float(similarities[i]),  # Convert numpy float32 to Python float
                    "content": document.content if hasattr(document, 'content') else document.synthesis_content,
                    "type": embedding_record.document_type,
                    "id": embedding_record.document_id
                })
        
        return results

    def _get_document_by_embedding(self, embedding_record: Embedding) -> Optional[Any]:
        """Retrieve the source document for an embedding record."""
        if embedding_record.document_type == 'kb_item':
            return KnowledgeBaseItem.query.get(embedding_record.document_id)
        elif embedding_record.document_type == 'synthesis':
            return SubcategorySynthesis.query.get(embedding_record.document_id)
        return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between two vectors."""
        vec1 = vec1.reshape(1, -1)
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2, axis=1)
        
        # Handle zero vectors
        denominator = norm1 * norm2
        denominator[denominator == 0] = 1e-9 # Avoid division by zero
        
        return np.dot(vec2, vec1.T).flatten() / denominator 

    async def _get_embedding_from_api(self, text: str) -> Optional[List[float]]:
        """Get embedding for a single text from the API."""
        try:
            embedding = await self.http_client.ollama_embed(
                model=self.embedding_model,
                prompt=text
            )
            return embedding
        except AIError as e:
            logging.error(f"Failed to get embedding from API: {e}")
            return None

    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """Normalize a vector to unit length."""
        vector_array = np.array(vector)
        norm = np.linalg.norm(vector_array)
        if norm == 0:
            return vector
        return (vector_array / norm).tolist() 