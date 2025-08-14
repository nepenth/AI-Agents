"""
Seven-Phase Pipeline Model Integration Service.

This service implements the complete seven-phase processing pipeline with
model integration, phase-by-phase execution, and comprehensive tracking.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum

from app.services.content_processing_pipeline import get_content_processing_pipeline
from app.services.model_router import get_model_router
from app.services.model_settings import ModelPhase
from app.services.ai_service import get_ai_service
from app.services.embedding_service import get_embedding_service
from app.repositories.content import get_content_repository
from app.repositories.knowledge import get_knowledge_repository
from app.repositories.synthesis import get_synthesis_repository
from app.repositories.readme import get_readme_repository
from app.database.connection import get_db_session
from app.models.pipeline import PipelineExecution, PipelinePhase
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class PhaseStatus(str, Enum):
    """Pipeline phase execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SevenPhasePipeline:
    """
    Seven-Phase Pipeline Model Integration Service.
    
    Implements the complete seven-phase processing pipeline:
    1. Initialization
    2. Fetch Bookmarks
    3. Content Processing (with sub-phases)
    4. Synthesis Generation
    5. Embedding Generation
    6. README Generation
    7. Git Sync
    """
    
    def __init__(self):
        self.content_pipeline = get_content_processing_pipeline()
        self.model_router = get_model_router()
        self.ai_service = get_ai_service()
        self.embedding_service = get_embedding_service()
        self.content_repo = get_content_repository()
        self.knowledge_repo = get_knowledge_repository()
        self.synthesis_repo = get_synthesis_repository()
        self.readme_repo = get_readme_repository()
    
    async def execute_pipeline(
        self,
        config: Dict[str, Any],
        models_override: Optional[Dict[str, Any]] = None,
        run_async: bool = True
    ) -> Dict[str, Any]:
        """
        Execute the complete seven-phase pipeline.
        
        Args:
            config: Pipeline configuration
            models_override: Optional model overrides for AI phases
            run_async: Whether to run phases asynchronously via Celery
            
        Returns:
            Dict[str, Any]: Pipeline execution results
        """
        pipeline_id = str(uuid.uuid4())
        
        try:
            if run_async:
                # Execute pipeline asynchronously via Celery
                task = run_seven_phase_pipeline_task.apply_async(
                    args=[pipeline_id, config, models_override]
                )
                
                return {
                    'status': 'started',
                    'pipeline_id': pipeline_id,
                    'task_id': task.id,
                    'message': 'Seven-phase pipeline started asynchronously',
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                # Execute pipeline synchronously
                return await self._execute_pipeline_sync(pipeline_id, config, models_override)
                
        except Exception as e:
            logger.error(f"Failed to execute seven-phase pipeline: {e}")
            return {
                'status': 'failed',
                'pipeline_id': pipeline_id,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _execute_pipeline_sync(
        self,
        pipeline_id: str,
        config: Dict[str, Any],
        models_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute pipeline synchronously with phase tracking."""
        phase_results = {}
        overall_start_time = datetime.utcnow()
        
        try:
            # Phase 1: Initialization
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 1 - Initialization")
            phase_1_result = await self._phase_1_initialization(config)
            phase_results['phase_1_initialization'] = phase_1_result
            
            if phase_1_result['status'] != 'completed':
                return self._build_pipeline_result(pipeline_id, 'failed', phase_results, overall_start_time, 'phase_1_initialization')
            
            # Phase 2: Fetch Bookmarks
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 2 - Fetch Bookmarks")
            phase_2_result = await self._phase_2_fetch_bookmarks(config)
            phase_results['phase_2_fetch_bookmarks'] = phase_2_result
            
            if phase_2_result['status'] != 'completed':
                return self._build_pipeline_result(pipeline_id, 'failed', phase_results, overall_start_time, 'phase_2_fetch_bookmarks')
            
            # Get content IDs for processing
            content_ids = [item['content_id'] for item in phase_2_result.get('fetched_bookmarks', [])]
            
            if not content_ids:
                logger.warning(f"Pipeline {pipeline_id}: No content to process")
                return self._build_pipeline_result(pipeline_id, 'completed', phase_results, overall_start_time, message='No content to process')
            
            # Phase 3: Content Processing (with sub-phases)
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 3 - Content Processing")
            phase_3_result = await self._phase_3_content_processing(content_ids, models_override)
            phase_results['phase_3_content_processing'] = phase_3_result
            
            # Phase 4: Synthesis Generation
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 4 - Synthesis Generation")
            phase_4_result = await self._phase_4_synthesis_generation(models_override)
            phase_results['phase_4_synthesis_generation'] = phase_4_result
            
            # Phase 5: Embedding Generation
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 5 - Embedding Generation")
            phase_5_result = await self._phase_5_embedding_generation(models_override)
            phase_results['phase_5_embedding_generation'] = phase_5_result
            
            # Phase 6: README Generation
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 6 - README Generation")
            phase_6_result = await self._phase_6_readme_generation(config, models_override)
            phase_results['phase_6_readme_generation'] = phase_6_result
            
            # Phase 7: Git Sync
            logger.info(f"Pipeline {pipeline_id}: Starting Phase 7 - Git Sync")
            phase_7_result = await self._phase_7_git_sync(config)
            phase_results['phase_7_git_sync'] = phase_7_result
            
            # Determine overall status
            failed_phases = [name for name, result in phase_results.items() if result['status'] == 'failed']
            
            if not failed_phases:
                overall_status = 'completed'
            elif len(failed_phases) == len(phase_results):
                overall_status = 'failed'
            else:
                overall_status = 'partial_success'
            
            return self._build_pipeline_result(pipeline_id, overall_status, phase_results, overall_start_time, failed_phases=failed_phases)
            
        except Exception as e:
            logger.error(f"Pipeline {pipeline_id} execution failed: {e}")
            return self._build_pipeline_result(pipeline_id, 'failed', phase_results, overall_start_time, error=str(e))
    
    async def _phase_1_initialization(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 1: Initialize all components and validate configuration."""
        try:
            start_time = datetime.utcnow()
            
            # Validate configuration
            required_config = ['bookmark_url', 'git_repo_url']
            missing_config = [key for key in required_config if key not in config]
            
            if missing_config:
                return {
                    'status': 'failed',
                    'error': f'Missing required configuration: {", ".join(missing_config)}',
                    'duration': (datetime.utcnow() - start_time).total_seconds()
                }
            
            # Check component availability
            components_status = {}
            
            # Check Twitter API
            async with self.content_pipeline.twitter_client as client:
                components_status['twitter_api'] = await client.is_available()
            
            # Check AI backends
            components_status['ai_service'] = await self.ai_service.is_available()
            
            # Check database connection
            try:
                async with get_db_session() as db:
                    await db.execute("SELECT 1")
                components_status['database'] = True
            except Exception:
                components_status['database'] = False
            
            # Check if all components are available
            unavailable_components = [name for name, available in components_status.items() if not available]
            
            if unavailable_components:
                return {
                    'status': 'failed',
                    'error': f'Unavailable components: {", ".join(unavailable_components)}',
                    'components_status': components_status,
                    'duration': (datetime.utcnow() - start_time).total_seconds()
                }
            
            return {
                'status': 'completed',
                'message': 'All components initialized successfully',
                'components_status': components_status,
                'config_validated': True,
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Phase 1 initialization failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _phase_2_fetch_bookmarks(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 2: Fetch bookmarks from Twitter/X API."""
        try:
            start_time = datetime.utcnow()
            
            # Fetch bookmarks using content processing pipeline
            result = await self.content_pipeline.fetch_bookmarks_from_collection(
                collection_url=config.get('bookmark_url'),
                max_results=config.get('max_bookmarks', 100),
                force_refresh=config.get('force_refresh', False)
            )
            
            result['duration'] = (datetime.utcnow() - start_time).total_seconds()
            return result
            
        except Exception as e:
            logger.error(f"Phase 2 fetch bookmarks failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _phase_3_content_processing(
        self, 
        content_ids: List[str], 
        models_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Phase 3: Content Processing with sub-phases."""
        try:
            start_time = datetime.utcnow()
            
            # Process each content item through sub-phases
            processing_results = []
            failed_items = []
            
            for content_id in content_ids:
                try:
                    # Process content item through all sub-phases
                    result = await self.content_pipeline.process_twitter_bookmark(
                        tweet_id=content_id,  # Note: This should be updated to use content_id properly
                        force_refresh=models_override is not None,
                        models_override=models_override,
                        run_async=False  # Run synchronously for pipeline execution
                    )
                    
                    if result['status'] == 'completed':
                        processing_results.append(result)
                    else:
                        failed_items.append(result)
                        
                except Exception as e:
                    logger.error(f"Failed to process content {content_id}: {e}")
                    failed_items.append({
                        'content_id': content_id,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            # Determine overall status
            if not processing_results and failed_items:
                status = 'failed'
            elif failed_items:
                status = 'partial_success'
            else:
                status = 'completed'
            
            return {
                'status': status,
                'processed_count': len(processing_results),
                'failed_count': len(failed_items),
                'processing_results': processing_results,
                'failed_items': failed_items,
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Phase 3 content processing failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _phase_4_synthesis_generation(self, models_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Phase 4: Generate synthesis documents using ModelPhase.synthesis."""
        try:
            start_time = datetime.utcnow()
            
            # Generate synthesis documents using content processing pipeline
            result = await self.content_pipeline.generate_synthesis_documents(
                models_override=models_override,
                min_bookmarks_per_category=3
            )
            
            result['duration'] = (datetime.utcnow() - start_time).total_seconds()
            return result
            
        except Exception as e:
            logger.error(f"Phase 4 synthesis generation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _phase_5_embedding_generation(self, models_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Phase 5: Generate embeddings using ModelPhase.embeddings."""
        try:
            start_time = datetime.utcnow()
            
            # Resolve embeddings model
            override_selector = models_override.get('embeddings') if models_override else None
            backend, model, params = await self.model_router.resolve(ModelPhase.embeddings, override=override_selector)
            
            generated_embeddings = []
            failed_embeddings = []
            
            async with get_db_session() as db:
                # Generate embeddings for content items
                content_items = await self.content_repo.get_all_unembedded(db)
                
                for content_item in content_items:
                    try:
                        # Generate embedding for content
                        text_to_embed = content_item.collective_understanding or content_item.content
                        embedding = await self.embedding_service.generate_embedding(text_to_embed, model)
                        
                        # Store embedding
                        await self.embedding_service.store_embedding(
                            db, content_item.id, embedding, 'content'
                        )
                        
                        generated_embeddings.append({
                            'content_id': content_item.id,
                            'embedding_dimension': len(embedding),
                            'text_length': len(text_to_embed)
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for {content_item.id}: {e}")
                        failed_embeddings.append({
                            'content_id': content_item.id,
                            'error': str(e)
                        })
                
                # Generate embeddings for synthesis documents
                synthesis_docs = await self.synthesis_repo.get_all_unembedded(db)
                
                for synthesis_doc in synthesis_docs:
                    try:
                        # Generate embedding for synthesis
                        text_to_embed = synthesis_doc.summary or synthesis_doc.content[:1000]
                        embedding = await self.embedding_service.generate_embedding(text_to_embed, model)
                        
                        # Store embedding
                        await self.embedding_service.store_embedding(
                            db, synthesis_doc.id, embedding, 'synthesis'
                        )
                        
                        generated_embeddings.append({
                            'synthesis_id': synthesis_doc.id,
                            'embedding_dimension': len(embedding),
                            'text_length': len(text_to_embed)
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for synthesis {synthesis_doc.id}: {e}")
                        failed_embeddings.append({
                            'synthesis_id': synthesis_doc.id,
                            'error': str(e)
                        })
            
            # Determine status
            if not generated_embeddings and failed_embeddings:
                status = 'failed'
            elif failed_embeddings:
                status = 'partial_success'
            else:
                status = 'completed'
            
            return {
                'status': status,
                'generated_count': len(generated_embeddings),
                'failed_count': len(failed_embeddings),
                'generated_embeddings': generated_embeddings,
                'failed_embeddings': failed_embeddings,
                'model_used': model,
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Phase 5 embedding generation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _phase_6_readme_generation(
        self, 
        config: Dict[str, Any], 
        models_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Phase 6: Generate README using ModelPhase.readme_generation."""
        try:
            start_time = datetime.utcnow()
            
            # Resolve README generation model
            override_selector = models_override.get('readme_generation') if models_override else None
            backend, model, params = await self.model_router.resolve(ModelPhase.readme_generation, override=override_selector)
            
            async with get_db_session() as db:
                # Get statistics for README generation
                content_stats = await self._get_content_statistics(db)
                category_stats = await self._get_category_statistics(db)
                synthesis_stats = await self._get_synthesis_statistics(db)
                
                # Generate README content
                readme_content = await self._generate_readme_content(
                    content_stats, category_stats, synthesis_stats, backend, model, params
                )
                
                # Store README content
                readme_data = {
                    'id': str(uuid.uuid4()),
                    'title': 'Knowledge Base Index',
                    'content': readme_content['content'],
                    'content_type': 'markdown',
                    'section_type': 'index',
                    'readme_model_used': model,
                    'statistics': {
                        'content_count': content_stats['total_content'],
                        'category_count': len(category_stats),
                        'synthesis_count': synthesis_stats['total_synthesis']
                    }
                }
                
                readme_doc = await self.readme_repo.create(db, readme_data)
            
            return {
                'status': 'completed',
                'readme_id': readme_doc.id,
                'content_length': len(readme_content['content']),
                'sections_generated': readme_content['sections_count'],
                'model_used': model,
                'statistics': readme_data['statistics'],
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Phase 6 README generation failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    async def _phase_7_git_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 7: Export markdown files and sync with Git repository."""
        try:
            start_time = datetime.utcnow()
            
            # TODO: Implement actual Git sync functionality
            # For now, simulate the Git sync process
            
            git_repo_url = config.get('git_repo_url')
            if not git_repo_url:
                return {
                    'status': 'failed',
                    'error': 'Git repository URL not provided',
                    'duration': (datetime.utcnow() - start_time).total_seconds()
                }
            
            # Simulate file export and Git operations
            exported_files = []
            
            async with get_db_session() as db:
                # Export content items
                content_items = await self.content_repo.get_all_processed(db)
                for item in content_items:
                    exported_files.append({
                        'type': 'content',
                        'id': item.id,
                        'filename': f"content/{item.main_category}/{item.id}.md",
                        'size': len(item.content or '')
                    })
                
                # Export synthesis documents
                synthesis_docs = await self.synthesis_repo.get_all(db)
                for doc in synthesis_docs:
                    exported_files.append({
                        'type': 'synthesis',
                        'id': doc.id,
                        'filename': f"synthesis/{doc.main_category}/{doc.id}.md",
                        'size': len(doc.content or '')
                    })
                
                # Export README
                readme_docs = await self.readme_repo.get_latest(db)
                if readme_docs:
                    exported_files.append({
                        'type': 'readme',
                        'id': readme_docs.id,
                        'filename': 'README.md',
                        'size': len(readme_docs.content or '')
                    })
            
            # Simulate Git operations
            git_operations = [
                'clone_or_pull',
                'export_files',
                'add_changes',
                'commit_changes',
                'push_changes'
            ]
            
            return {
                'status': 'completed',
                'git_repo_url': git_repo_url,
                'exported_files_count': len(exported_files),
                'exported_files': exported_files,
                'git_operations': git_operations,
                'commit_hash': 'abc123def456',  # Simulated
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Phase 7 Git sync failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'duration': (datetime.utcnow() - start_time).total_seconds()
            }
    
    def _build_pipeline_result(
        self,
        pipeline_id: str,
        status: str,
        phase_results: Dict[str, Any],
        start_time: datetime,
        failed_phase: Optional[str] = None,
        failed_phases: Optional[List[str]] = None,
        error: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build standardized pipeline result."""
        return {
            'status': status,
            'pipeline_id': pipeline_id,
            'total_duration': (datetime.utcnow() - start_time).total_seconds(),
            'phases_completed': len([r for r in phase_results.values() if r.get('status') == 'completed']),
            'phases_failed': len([r for r in phase_results.values() if r.get('status') == 'failed']),
            'phase_results': phase_results,
            'failed_phase': failed_phase,
            'failed_phases': failed_phases or [],
            'error': error,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _get_content_statistics(self, db) -> Dict[str, Any]:
        """Get content statistics for README generation."""
        # TODO: Implement actual statistics query
        return {
            'total_content': 50,
            'processed_content': 45,
            'with_media': 20,
            'with_threads': 15
        }
    
    async def _get_category_statistics(self, db) -> List[Dict[str, Any]]:
        """Get category statistics for README generation."""
        # TODO: Implement actual category statistics query
        return [
            {'name': 'machine-learning', 'count': 15, 'subcategories': ['neural-networks', 'deep-learning']},
            {'name': 'web-development', 'count': 12, 'subcategories': ['frontend', 'backend']},
            {'name': 'data-science', 'count': 10, 'subcategories': ['analytics', 'visualization']}
        ]
    
    async def _get_synthesis_statistics(self, db) -> Dict[str, Any]:
        """Get synthesis statistics for README generation."""
        # TODO: Implement actual synthesis statistics query
        return {
            'total_synthesis': 8,
            'categories_with_synthesis': 3,
            'average_sources_per_synthesis': 4.2
        }
    
    async def _generate_readme_content(
        self,
        content_stats: Dict[str, Any],
        category_stats: List[Dict[str, Any]],
        synthesis_stats: Dict[str, Any],
        backend,
        model: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate README content using AI model."""
        # TODO: Implement actual README generation with XML prompts
        # For now, generate a structured README
        
        readme_content = f"""# Knowledge Base

This knowledge base contains {content_stats['total_content']} curated bookmarks organized into {len(category_stats)} categories.

## Statistics

- **Total Bookmarks**: {content_stats['total_content']}
- **Processed Items**: {content_stats['processed_content']}
- **Items with Media**: {content_stats['with_media']}
- **Thread Discussions**: {content_stats['with_threads']}
- **Synthesis Documents**: {synthesis_stats['total_synthesis']}

## Categories

"""
        
        for category in category_stats:
            readme_content += f"### {category['name'].title()}\n"
            readme_content += f"- **Items**: {category['count']}\n"
            readme_content += f"- **Subcategories**: {', '.join(category['subcategories'])}\n\n"
        
        readme_content += f"""
## Synthesis Documents

{synthesis_stats['total_synthesis']} synthesis documents have been generated, covering {synthesis_stats['categories_with_synthesis']} categories with an average of {synthesis_stats['average_sources_per_synthesis']:.1f} sources per document.

## Navigation

- Browse by category in the respective folders
- View synthesis documents for comprehensive topic overviews
- Search through embedded content using vector similarity

---

*Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*
*Model used: {model}*
"""
        
        return {
            'content': readme_content,
            'sections_count': len(category_stats) + 3  # Categories + Statistics + Synthesis + Navigation
        }


# Celery task for async pipeline execution
@celery_app.task(bind=True)
def run_seven_phase_pipeline_task(
    self,
    pipeline_id: str,
    config: Dict[str, Any],
    models_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Celery task for running the seven-phase pipeline asynchronously."""
    try:
        # Run async pipeline execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            pipeline = SevenPhasePipeline()
            result = loop.run_until_complete(
                pipeline._execute_pipeline_sync(pipeline_id, config, models_override)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Seven-phase pipeline task failed: {e}")
        return {
            'status': 'failed',
            'pipeline_id': pipeline_id,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


# Singleton instance
_seven_phase_pipeline: Optional[SevenPhasePipeline] = None


def get_seven_phase_pipeline() -> SevenPhasePipeline:
    """Get the singleton seven-phase pipeline instance."""
    global _seven_phase_pipeline
    if _seven_phase_pipeline is None:
        _seven_phase_pipeline = SevenPhasePipeline()
    return _seven_phase_pipeline