"""
Enhanced Embedding Manager Module

This module provides sophisticated embedding management with vector store support,
automatic migration from SQL storage, and optimized embedding creation strategies.
"""

import logging
import asyncio
import os
import time
from typing import List, Optional, Tuple, Dict, Any, Union
from datetime import datetime, timezone
import numpy as np
from pathlib import Path

# Chroma imports
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from .config import Config
from .http_client import HTTPClient
from .models import db, KnowledgeBaseItem, SubcategorySynthesis, Embedding
from .custom_types import Synthesis
from .file_utils import async_json_load, async_write_text
from .exceptions import AIError

class EmbeddingManager:
    """Enhanced embedding manager with vector store support and optimization."""

    def __init__(self, config: Config, http_client: HTTPClient):
        self.config = config
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
        self.embedding_model = config.embedding_model
        
        # Vector store configuration
        self.use_vector_store = CHROMA_AVAILABLE and hasattr(config, 'vector_store_path') and bool(getattr(config, 'vector_store_path', None))
        self.vector_store_path = getattr(config, 'vector_store_path', './data/vector_store') if self.use_vector_store else None
        self.collection_name = getattr(config, 'vector_collection_name', 'knowledge_base') if self.use_vector_store else "knowledge_base"
        
        # Initialize vector store
        self.chroma_client = None
        self.collection = None
        
        if self.use_vector_store:
            self._initialize_chroma()
        else:
            self.logger.info("Using SQL storage for embeddings (Chroma not available or not configured)")

    def _initialize_chroma(self):
        """Initialize Chroma vector database."""
        try:
            # Ensure vector store directory exists
            if self.vector_store_path:
                store_path = Path(self.vector_store_path)
                store_path.mkdir(parents=True, exist_ok=True)
            
                # Initialize Chroma client using the new configuration method
                # This fixes the deprecation warning about old configuration
                self.chroma_client = chromadb.PersistentClient(
                    path=str(store_path),
                    settings=Settings(anonymized_telemetry=False)
                )
                
                # Get or create collection without embedding function
                try:
                    self.collection = self.chroma_client.get_collection(name=self.collection_name)
                    self.logger.info(f"Connected to existing Chroma collection: {self.collection_name}")
                except Exception:
                    self.collection = self.chroma_client.create_collection(name=self.collection_name)
                    self.logger.info(f"Created new Chroma collection: {self.collection_name}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Chroma: {e}")
            self.logger.info("Falling back to SQL storage")
            self.use_vector_store = False

    async def migrate_sql_to_vector_store(self) -> Tuple[int, int]:
        """Migrate existing SQL embeddings to vector store."""
        if not self.use_vector_store or not self.collection:
            self.logger.warning("Vector store not available for migration")
            return 0, 0
            
        self.logger.info("Starting migration from SQL to vector store...")
        
        # Get all existing SQL embeddings
        sql_embeddings = Embedding.query.filter_by(model=self.embedding_model).all()
        
        migrated_count = 0
        error_count = 0
        
        for sql_embedding in sql_embeddings:
            try:
                # Get the source document
                document = self._get_document_by_embedding(sql_embedding)
                if not document:
                    self.logger.warning(f"Document not found for embedding {sql_embedding.id}")
                    continue
                
                # Convert binary embedding back to vector
                embedding_vector = np.frombuffer(sql_embedding.embedding, dtype=np.float32).tolist()
                
                # Create metadata
                metadata = self._create_document_metadata_safe(document, sql_embedding.document_type)
                
                # Add to vector store
                self.collection.add(
                    embeddings=[embedding_vector],
                    documents=[self._get_document_content_safe(document)],
                    metadatas=[metadata],
                    ids=[f"{sql_embedding.document_type}_{sql_embedding.document_id}"]
                )
                
                migrated_count += 1
                self.logger.debug(f"Migrated {sql_embedding.document_type} {sql_embedding.document_id}")
                
            except Exception as e:
                self.logger.error(f"Error migrating embedding {sql_embedding.id}: {e}")
                error_count += 1
        
        self.logger.info(f"Migration complete: {migrated_count} embeddings migrated, {error_count} errors")
        return migrated_count, error_count

    async def generate_all_embeddings(
        self,
        force_regenerate: bool = False,
        phase_emitter_func=None
    ) -> Tuple[int, int]:
        """
        Generate embeddings for all KB items and synthesis documents with enhanced optimization.
        """
        self.logger.info("Starting optimized embedding generation for all documents.")
        
        # If using vector store and force regenerate, migrate existing first
        if self.use_vector_store and not force_regenerate:
            await self.migrate_sql_to_vector_store()
        
        items_to_process = []
        
        # Get all KB items with optimized content extraction
        kb_items = KnowledgeBaseItem.query.all()
        for item in kb_items:
            content = self._extract_optimized_content(item, 'kb_item')
            if content:  # Only process items with meaningful content
                items_to_process.append({
                    'type': 'kb_item', 
                    'id': item.id, 
                    'content': content, 
                    'title': item.title,
                    'document': item
                })
            
        # Get all synthesis documents
        syntheses = SubcategorySynthesis.query.all()
        for synth in syntheses:
            content = self._extract_optimized_content(synth, 'synthesis')
            if content:
                items_to_process.append({
                    'type': 'synthesis', 
                    'id': synth.id, 
                    'content': content, 
                    'title': synth.synthesis_title,
                    'document': synth
                })

        total_items = len(items_to_process)
        self.logger.info(f"Found {total_items} documents to process for embeddings.")

        if phase_emitter_func:
            phase_emitter_func(
                "embedding_generation",
                "in_progress",
                f"Generating embeddings for {total_items} documents using {'Chroma vector store' if self.use_vector_store else 'SQL storage'}.",
                is_sub_step_update=False,
                processed_count=0,
                total_count=total_items,
                error_count=0
            )

        processed_count = 0
        error_count = 0
        batch_size = 10  # Process in batches for better performance

        for i in range(0, total_items, batch_size):
            batch = items_to_process[i:i + batch_size]
            
            # Process batch
            for item_data in batch:
                try:
                    # Skip if already exists (unless force regenerating)
                    if not force_regenerate and await self._embedding_exists(item_data):
                        self.logger.debug(f"Skipping existing embedding for {item_data['type']} {item_data['id']}")
                        processed_count += 1
                        continue

                    # Generate embedding with retry logic
                    start_time = time.time()
                    embedding_vector = await self._generate_embedding_with_retry(item_data['content'])
                    generation_time = time.time() - start_time
                    
                    # Save embedding
                    await self._save_embedding_optimized(
                        item_data=item_data,
                        embedding_vector=embedding_vector
                    )
                    
                    self.logger.debug(f"Generated embedding for {item_data['type']} {item_data['id']} in {generation_time:.2f}s")
                    processed_count += 1
                    
                    if phase_emitter_func:
                        phase_emitter_func(
                            "embedding_generation",
                            f"Processing item {processed_count}/{total_items}",
                            "in_progress",
                            is_sub_step_update=True,
                            processed_count=processed_count,
                            total_count=total_items,
                            error_count=error_count
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error generating embedding for {item_data['type']} {item_data['id']}: {e}", exc_info=True)
                    error_count += 1

            # Small delay between batches to avoid overwhelming the API
            await asyncio.sleep(0.1)

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
                    f"Successfully generated embeddings for {processed_count} documents using {'Chroma vector store' if self.use_vector_store else 'SQL storage'}.",
                    is_sub_step_update=False,
                    processed_count=processed_count,
                    total_count=total_items,
                    error_count=error_count
                )
        
        return processed_count, error_count

    def _extract_optimized_content(self, document: Union[KnowledgeBaseItem, SubcategorySynthesis], doc_type: str) -> Optional[str]:
        """Extract and optimize content for embedding generation."""
        try:
            if doc_type == 'kb_item':
                # For KB items, combine title, description, and content for richer context
                parts = []
                if hasattr(document, 'display_title') and document.display_title:
                    parts.append(f"Title: {document.display_title}")
                if hasattr(document, 'description') and document.description:
                    parts.append(f"Description: {document.description}")
                if hasattr(document, 'content') and document.content:
                    # Clean and truncate content
                    content = document.content.strip()
                    # Remove excessive whitespace
                    content = ' '.join(content.split())
                    # Truncate if too long (embeddings have token limits)
                    if len(content) > 8000:  # Conservative limit for embedding models
                        content = content[:8000] + "..."
                    parts.append(content)
                    
                return '\n\n'.join(parts) if parts else None
                
            elif doc_type == 'synthesis':
                # For syntheses, use title + content
                parts = []
                if hasattr(document, 'synthesis_title') and document.synthesis_title:
                    parts.append(f"Title: {document.synthesis_title}")
                if hasattr(document, 'synthesis_content') and document.synthesis_content:
                    content = document.synthesis_content.strip()
                    content = ' '.join(content.split())
                    if len(content) > 8000:
                        content = content[:8000] + "..."
                    parts.append(content)
                    
                return '\n\n'.join(parts) if parts else None
                
        except Exception as e:
            self.logger.error(f"Error extracting content from {doc_type}: {e}")
            
        return None

    async def _generate_embedding_with_retry(self, content: str, max_retries: int = 3) -> List[float]:
        """Generate embedding with retry logic and validation."""
        
        for attempt in range(max_retries):
            try:
                # Validate content before sending to API
                if not content or not content.strip():
                    raise ValueError("Content is empty or whitespace-only")
                
                content_length = len(content)
                content_preview = content[:100] + "..." if len(content) > 100 else content
                self.logger.debug(f"Generating embedding for content (length={content_length}, attempt={attempt+1}): {content_preview}")
                
                embedding = await self.http_client.ollama_embed(
                    model=self.embedding_model,
                    prompt=content
                )
                
                if not embedding or len(embedding) == 0:
                    raise ValueError(f"Received empty embedding from API for content: {content_preview}")
                
                # Validate embedding dimensionality
                if len(embedding) < 100:  # Most embedding models have at least 100 dimensions
                    raise ValueError(f"Embedding dimension too small: {len(embedding)}")
                
                self.logger.debug(f"Successfully generated embedding with dimension {len(embedding)}")
                return embedding
                
            except Exception as e:
                self.logger.warning(f"Embedding generation attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to generate embedding after {max_retries} attempts")
                    raise Exception(f"Failed to generate embedding from API: {e}")
                else:
                    # Wait before retry
                    await asyncio.sleep(1 * (attempt + 1))

    async def _embedding_exists(self, item_data: Dict[str, Any]) -> bool:
        """Check if embedding already exists for the item."""
        try:
            if self.use_vector_store:
                # Check Chroma collection
                doc_id = f"{item_data['type']}_{item_data['id']}"
                try:
                    result = self.collection.get(ids=[doc_id])
                    return len(result['ids']) > 0
                except Exception:
                    return False
            else:
                # Check SQL database
                existing_embedding = Embedding.query.filter_by(
                    document_id=item_data['id'],
                    document_type=item_data['type'],
                    model=self.embedding_model
                ).first()
                return existing_embedding is not None
        except Exception as e:
            self.logger.warning(f"Error checking embedding existence: {e}")
            return False

    async def _save_embedding_optimized(self, item_data: Dict[str, Any], embedding_vector: List[float]):
        """Save embedding using the optimal storage method."""
        
        if self.use_vector_store:
            await self._save_to_vector_store(item_data, embedding_vector)
        else:
            await self._save_to_sql(item_data, embedding_vector)

    async def _save_to_vector_store(self, item_data: Dict[str, Any], embedding_vector: List[float]):
        """Save embedding to Chroma vector store."""
        try:
            doc_id = f"{item_data['type']}_{item_data['id']}"
            metadata = self._create_document_metadata(item_data['document'], item_data['type'])
            
            # Update or add to collection
            try:
                # Try to update first
                self.collection.update(
                    ids=[doc_id],
                    embeddings=[embedding_vector],
                    documents=[item_data['content']],
                    metadatas=[metadata]
                )
            except Exception:
                # If update fails, add new
                self.collection.add(
                    ids=[doc_id],
                    embeddings=[embedding_vector],
                    documents=[item_data['content']],
                    metadatas=[metadata]
                )
                
        except Exception as e:
            self.logger.error(f"Error saving to vector store: {e}")
            raise

    async def _save_to_sql(self, item_data: Dict[str, Any], embedding_vector: List[float]):
        """Save embedding to SQL database (legacy method)."""
        
        existing_embedding = Embedding.query.filter_by(
            document_id=item_data['id'],
            document_type=item_data['type'],
            model=self.embedding_model
        ).first()

        embedding_bytes = np.array(embedding_vector).astype(np.float32).tobytes()

        if existing_embedding:
            existing_embedding.embedding = embedding_bytes
            existing_embedding.created_at = datetime.now(timezone.utc)
        else:
            new_embedding = Embedding(
                document_id=item_data['id'],
                document_type=item_data['type'],
                embedding=embedding_bytes,
                model=self.embedding_model,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_embedding)
        
        db.session.commit()

    def _create_document_metadata(self, document: Union[KnowledgeBaseItem, SubcategorySynthesis], doc_type: str) -> Dict[str, Any]:
        """Create comprehensive metadata for vector store."""
        metadata = {
            'document_type': doc_type,
            'model': self.embedding_model,
            'created_at': str(datetime.now(timezone.utc)),
        }
        
        if doc_type == 'kb_item':
            metadata.update({
                'title': getattr(document, 'display_title', ''),
                'description': getattr(document, 'description', ''),
                'category': getattr(document, 'category_info', {}).get('category', '') if hasattr(document, 'category_info') else '',
                'subcategory': getattr(document, 'category_info', {}).get('subcategory', '') if hasattr(document, 'category_info') else '',
            })
        elif doc_type == 'synthesis':
            metadata.update({
                'title': getattr(document, 'synthesis_title', ''),
                'category': getattr(document, 'category', ''),
                'subcategory': getattr(document, 'subcategory', ''),
            })
        
        return metadata

    def _get_document_content(self, document: Union[KnowledgeBaseItem, SubcategorySynthesis]) -> str:
        """Get document content for vector store."""
        if hasattr(document, 'content'):
            return document.content or ''
        elif hasattr(document, 'synthesis_content'):
            return document.synthesis_content or ''
        return ''

    async def find_similar_documents(self, query: str, top_k: int = 5, include_scores: bool = True) -> List[Dict[str, Any]]:
        """Find similar documents with enhanced search capabilities."""
        self.logger.info(f"Searching for documents similar to: '{query}'")

        if self.use_vector_store:
            return await self._search_vector_store(query, top_k, include_scores)
        else:
            return await self._search_sql_embeddings(query, top_k)

    async def _search_vector_store(self, query: str, top_k: int, include_scores: bool) -> List[Dict[str, Any]]:
        """Search using Chroma vector store."""
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding_with_retry(query)
            
            # Search in vector store
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances']
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                doc_id = results['ids'][0][i]
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                
                # Convert distance to similarity score (assuming cosine distance)
                similarity_score = 1 - distance
                
                # Get the actual document
                doc_type, doc_id_num = doc_id.split('_', 1)
                document = self._get_document_by_id(int(doc_id_num), doc_type)
                
                if document:
                    result = {
                        "title": metadata.get('title', ''),
                        "score": float(similarity_score),
                        "content": self._get_document_content(document),
                        "type": doc_type,
                        "id": int(doc_id_num),
                        "category": metadata.get('category', ''),
                        "subcategory": metadata.get('subcategory', ''),
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Error searching vector store: {e}")
            return []

    async def _search_sql_embeddings(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Search using SQL embeddings (legacy method)."""
        query_embedding = await self._generate_embedding_with_retry(query)
        
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
                    "score": float(similarities[i]),
                    "content": document.content if hasattr(document, 'content') else document.synthesis_content,
                    "type": embedding_record.document_type,
                    "id": embedding_record.document_id
                })
        
        return results

    def _get_document_by_id(self, doc_id: int, doc_type: str) -> Optional[Union[KnowledgeBaseItem, SubcategorySynthesis]]:
        """Get document by ID and type."""
        if doc_type == 'kb_item':
            return KnowledgeBaseItem.query.get(doc_id)
        elif doc_type == 'synthesis':
            return SubcategorySynthesis.query.get(doc_id)
        return None

    def _get_document_by_embedding(self, embedding_record: Embedding) -> Optional[Any]:
        """Retrieve the source document for an embedding record."""
        return self._get_document_by_id(embedding_record.document_id, embedding_record.document_type)

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between two vectors."""
        vec1 = vec1.reshape(1, -1)
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2, axis=1)
        
        # Handle zero vectors
        denominator = norm1 * norm2
        denominator[denominator == 0] = 1e-9 # Avoid division by zero
        
        return np.dot(vec2, vec1.T).flatten() / denominator 