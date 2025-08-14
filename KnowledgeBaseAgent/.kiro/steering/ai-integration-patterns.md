# AI Integration Patterns

This document provides guidelines for integrating AI capabilities throughout the backend system.

## AI Service Architecture

### 1. Provider Abstraction Layer

The system supports multiple AI providers through a unified interface:

```python
# Base AI interface that all providers implement
class BaseAIProvider:
    async def generate_text(self, prompt: str, config: GenerationConfig) -> str
    async def generate_stream(self, prompt: str, config: GenerationConfig) -> AsyncGenerator[str, None]
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]
```

**Supported Providers:**
- **Ollama**: Local AI models for privacy and control
- **LocalAI**: OpenAI-compatible local inference
- **OpenAI Compatible**: Any OpenAI-compatible API

### 2. AI Service Factory Pattern

Use the factory pattern to create AI service instances:

```python
ai_service = get_ai_service()  # Returns configured provider
embeddings = await ai_service.generate_embeddings(["text1", "text2"])
```

### 3. Configuration Management

AI providers are configured through environment variables and can be overridden at runtime via API model settings. Support per-phase model selection: `vision`, `kb_generation`, `synthesis`, `chat`, `embeddings`.

```bash
# Ollama Configuration
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# OpenAI Compatible Configuration  
AI_PROVIDER=openai_compatible
OPENAI_API_BASE=http://localhost:8080/v1
OPENAI_API_KEY=your-api-key

# Phase defaults (optional; can be set via API instead)
PHASE_MODEL_VISION_BACKEND=ollama
PHASE_MODEL_VISION_MODEL=llava:13b

PHASE_MODEL_KB_GENERATION_BACKEND=localai
PHASE_MODEL_KB_GENERATION_MODEL=mixtral:8x7b

PHASE_MODEL_SYNTHESIS_BACKEND=ollama
PHASE_MODEL_SYNTHESIS_MODEL=qwen2.5:7b

PHASE_MODEL_CHAT_BACKEND=ollama
PHASE_MODEL_CHAT_MODEL=llama3.1:8b-instruct

PHASE_MODEL_EMBEDDINGS_BACKEND=openai
PHASE_MODEL_EMBEDDINGS_MODEL=text-embedding-3-small
```

## Content Processing Pipeline

### 1. Automated Content Enhancement

When content is created or updated, it automatically goes through AI processing:

```python
# Content creation triggers AI processing
content_item = await content_service.create(content_data)

# Background task for AI enhancement
enhance_content_task.delay(content_item.id)
```

**Seven-Phase Processing Pipeline:**
1. **Phase 1 (Initialization)**: System setup and configuration validation
2. **Phase 2 (Fetch Bookmarks)**: Twitter/X API integration and bookmark retrieval
   - **Sub-phase 2.1 (Bookmark Caching)**: Thread detection, media caching, ground-truth storage
3. **Phase 3 (Content Processing)**: Multi-stage AI analysis with three sub-phases
   - **Sub-phase 3.1 (Media Analysis - vision)**: Vision model analysis of images/videos
   - **Sub-phase 3.2 (AI Content Understanding - kb_generation)**: Collective understanding generation
   - **Sub-phase 3.3 (AI Categorization - kb_generation)**: Category and sub-category assignment
4. **Phase 4 (Synthesis Generation - synthesis)**: AI-powered synthesis document creation
5. **Phase 5 (Embedding Generation - embeddings)**: Vector database population for semantic search
6. **Phase 6 (README Generation - kb_generation)**: Dynamic README creation with navigation tree
7. **Phase 7 (Git Sync)**: Repository export with markdown file generation

Each phase uses appropriate AI models through the ModelRouter system with intelligent processing logic to avoid unnecessary reprocessing.

### 2. Knowledge Graph Construction

AI helps build a knowledge graph from content:

```python
# Extract entities and relationships
entities = await ai_service.extract_entities(content.text)
relationships = await ai_service.extract_relationships(content.text)

# Build knowledge graph
await knowledge_service.add_entities(entities)
await knowledge_service.add_relationships(relationships)
```

### 3. Content Synthesis

Generate synthesis documents from multiple sources:

```python
# Gather related content
related_content = await content_service.get_related(topic, limit=10)

# Generate synthesis
synthesis = await ai_service.synthesize_content(
    sources=related_content,
    focus_topic=topic,
    target_audience="technical"
)

# Synthesis uses phase routing (synthesis)
backend, model, params = await model_router.resolve(ModelPhase.synthesis)
result = await backend.generate_text(prompt, model=model, **params)
```

## Vector Search Integration

### 1. Embedding Generation

All content automatically gets vector embeddings:

```python
class EmbeddingService:
    async def generate_embeddings(self, content: str) -> List[float]:
        # Chunk content for better embeddings
        chunks = self.chunk_content(content)
        
        # Generate embeddings for each chunk
        embeddings = []
        for chunk in chunks:
            embedding = await self.ai_service.generate_embeddings([chunk])
            embeddings.extend(embedding)
        
        return embeddings
```

### 2. Hybrid Search

Combine traditional text search with vector similarity:

```python
class VectorSearchService:
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        if query.search_type == SearchType.HYBRID:
            # Combine text and vector search
            text_results = await self.text_search(query.query_text)
            vector_results = await self.vector_search(query.query_text)
            
            # Merge and rank results
            return self.merge_results(text_results, vector_results)
```

### 3. Semantic Similarity

Find semantically similar content:

```python
# Find similar content based on vector similarity
similar_items = await vector_search_service.find_similar(
    content_id="item-123",
    similarity_threshold=0.8,
    limit=10
)
```

## Chat and Conversation AI

### 1. Context-Aware Responses

Chat system uses knowledge base for context:

```python
class ChatService:
    async def generate_response(self, message: str, session_id: str) -> str:
        # Get conversation context
        context = await self.build_conversation_context(session_id, message)
        
        # Search knowledge base for relevant information
        relevant_info = await self.search_knowledge_base(message)
        
        # Generate AI response with context
        backend, model, params = await model_router.resolve(
            ModelPhase.chat,
            override=session.model_override  # optional per-session override
        )
        response = await backend.generate_text(
            prompt=self.build_prompt(context, relevant_info, message),
            model=model,
            **params
        )
        
        return response
```

### 2. Streaming Responses

Support real-time streaming for better user experience:

```python
async def stream_chat_response(message: str) -> AsyncGenerator[str, None]:
    async for chunk in ai_service.generate_stream(prompt, config):
        # Send chunk via WebSocket
        await websocket_manager.send_message(user_id, {
            "type": "chat_chunk",
            "content": chunk
        })
        yield chunk
```

### 3. Conversation Memory

Maintain conversation context across messages:

```python
# Build conversation context with recent messages
recent_messages = await chat_repo.get_recent_messages(session_id, limit=10)
context = self.format_conversation_context(recent_messages)

# Include relevant knowledge base information
knowledge_context = await self.get_relevant_knowledge(message)
```

## AI Task Processing

### 1. Background AI Tasks

Long-running AI operations use Celery:

```python
@celery_app.task(bind=True)
def process_content_ai_task(self, content_id: str):
    """Background task for AI content processing."""
    try:
        # Update task progress
        self.update_state(state='PROGRESS', meta={'progress': 0})
        
        # Process content with AI
        content = get_content_by_id(content_id)
        
        # Generate embeddings (25% progress)
        embeddings = generate_embeddings(content.text)
        self.update_state(state='PROGRESS', meta={'progress': 25})
        
        # Extract entities (50% progress)
        entities = extract_entities(content.text)
        self.update_state(state='PROGRESS', meta={'progress': 50})
        
        # Generate summary (75% progress)
        summary = generate_summary(content.text)
        self.update_state(state='PROGRESS', meta={'progress': 75})
        
        # Save results (100% progress)
        save_ai_results(content_id, embeddings, entities, summary)
        
        return {'status': 'completed', 'progress': 100}
        
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
```

### 2. Task Progress Tracking

Monitor AI task progress with WebSocket updates:

```python
# Task progress notification
await notification_service.notify_task_progress(task_id, {
    'progress': 50,
    'stage': 'generating_embeddings',
    'message': 'Processing content embeddings...'
})
```

### 3. Error Handling and Retries

Robust error handling for AI operations:

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_with_retry(prompt: str) -> str:
    try:
        return await ai_service.generate_text(prompt)
    except AIServiceError as e:
        logger.warning(f"AI service error, retrying: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in AI generation: {e}")
        raise
```

## AI Model Management

### 1. Phase-Specific Model Routing

Choose appropriate models for different phases and support fallback if a model is unavailable. Cache capabilities per provider.

```python
class ModelPhase(str, Enum):
    vision = "vision"
    kb_generation = "kb_generation"
    synthesis = "synthesis"
    chat = "chat"
    embeddings = "embeddings"

class PhaseModelSelector(BaseModel):
    backend: Literal['ollama','localai','openai']
    model: str
    params: dict = {}

backend, model, params = await model_router.resolve(ModelPhase.chat)
response = await backend.generate_text(prompt=prompt, model=model, **params)
```

### 2. Provider Capability Discovery

Detect per-model capabilities to validate routing choices:
- Ollama: query `/api/tags` or `/api/models` to infer modalities and families (vision, instruct, embeddings)
- LocalAI: inspect model registry metadata; fall back to configuration when metadata is missing
- OpenAI-compatible: static mapping based on known model prefixes

Cache capability data in Redis with short TTL; refresh on cache miss.

### 3. Model Performance Monitoring

Track AI model performance and usage:

```python
class AIMetrics:
    async def track_generation(self, model: str, tokens: int, duration: float):
        # Track model usage metrics
        await self.metrics_service.increment_counter(
            "ai_generations_total",
            tags={"model": model}
        )
        
        await self.metrics_service.record_histogram(
            "ai_generation_duration_seconds",
            duration,
            tags={"model": model}
        )
```

### 4. Model Fallback Strategy

Implement fallback for model failures:

```python
async def generate_with_fallback(prompt: str) -> str:
    primary_model = "llama2:13b"
    fallback_model = "llama2:7b"
    
    try:
        return await ai_service.generate_text(prompt, model=primary_model)
    except AIServiceError:
        logger.warning(f"Primary model {primary_model} failed, using fallback")
        return await ai_service.generate_text(prompt, model=fallback_model)

## Twitter/X-Specific AI Processing

### 1. Thread Detection and Analysis

Process Twitter/X threads as cohesive units:

```python
class ThreadProcessor:
    async def detect_and_process_thread(self, tweet_id: str) -> ThreadInfo:
        # Detect if tweet is part of a thread
        thread_info = await self.twitter_client.get_thread_info(tweet_id)
        
        if thread_info.is_thread:
            # Process entire thread as a unit
            thread_content = await self.process_thread_content(thread_info.tweets)
            
            # Generate collective understanding for thread
            backend, model, params = await model_router.resolve(ModelPhase.kb_generation)
            understanding = await backend.generate_text(
                prompt=self.build_thread_understanding_prompt(thread_content),
                model=model,
                **params
            )
            
            return ThreadInfo(
                thread_id=thread_info.thread_id,
                collective_understanding=understanding,
                tweet_count=len(thread_info.tweets)
            )
```

### 2. Media Analysis Integration

Analyze Twitter/X media content using vision models:

```python
class TwitterMediaProcessor:
    async def analyze_tweet_media(self, content_item: ContentItem) -> MediaAnalysisResult:
        if not content_item.media_content:
            return MediaAnalysisResult(has_media=False)
        
        # Get vision model for media analysis
        backend, model, params = await model_router.resolve(ModelPhase.vision)
        
        media_analyses = []
        for media_item in content_item.media_content:
            # Generate XML prompt for media analysis
            prompt = self.build_media_analysis_prompt(
                media_url=media_item['url'],
                media_type=media_item['type'],
                tweet_context=content_item.content
            )
            
            analysis = await backend.generate_text(prompt, model=model, **params)
            media_analyses.append({
                'media_id': media_item['id'],
                'analysis': analysis,
                'model_used': model
            })
        
        # Store analysis results
        content_item.media_analysis_results = media_analyses
        content_item.vision_model_used = model
        content_item.media_analyzed = True
        
        return MediaAnalysisResult(
            has_media=True,
            analyses=media_analyses,
            model_used=model
        )
```

### 3. XML-Based Prompting System

Use structured XML prompts for consistent AI interactions:

```python
class XMLPromptBuilder:
    def build_media_analysis_prompt(self, media_url: str, media_type: str, tweet_context: str) -> str:
        return f"""
        <task>
            <instruction>Analyze the {media_type} content and provide detailed description</instruction>
            <context>
                <tweet_text>{tweet_context}</tweet_text>
                <media_url>{media_url}</media_url>
                <media_type>{media_type}</media_type>
            </context>
            <output_format>
                <description>Detailed visual description</description>
                <key_elements>List of important visual elements</key_elements>
                <relevance_to_tweet>How the media relates to the tweet text</relevance_to_tweet>
            </output_format>
        </task>
        """
    
    def build_content_understanding_prompt(self, content: str, media_analysis: Optional[str] = None) -> str:
        media_section = f"<media_analysis>{media_analysis}</media_analysis>" if media_analysis else ""
        
        return f"""
        <task>
            <instruction>Generate collective understanding of this Twitter/X content</instruction>
            <context>
                <tweet_content>{content}</tweet_content>
                {media_section}
            </context>
            <output_format>
                <main_topic>Primary topic or theme</main_topic>
                <key_insights>Important insights or takeaways</key_insights>
                <technical_details>Technical information if applicable</technical_details>
                <context_relevance>Why this content is valuable</context_relevance>
            </output_format>
        </task>
        """
```

## Provenance Tracking

Record which models are used per phase for auditability and evaluation:
- `content_items.vision_model_used` (Phase 3.1 - Media Analysis)
- `content_items.understanding_model_used` (Phase 3.2 - Content Understanding)
- `content_items.categorization_model_used` (Phase 3.3 - AI Categorization)
- `synthesis_documents.synthesis_model_used` (Phase 4 - Synthesis Generation)
- `content_items.embeddings_model_used` (Phase 5 - Embedding Generation)
- `readme_documents.generation_model_used` (Phase 6 - README Generation)
- `chat_messages.model_used` (Chat Interface)

Populate these fields in the corresponding services/tasks when each phase executes successfully.
```

## AI Quality and Safety

### 1. Content Filtering

Filter AI-generated content for safety:

```python
class ContentFilter:
    async def filter_content(self, content: str) -> FilterResult:
        # Check for inappropriate content
        if self.contains_harmful_content(content):
            return FilterResult(allowed=False, reason="harmful_content")
        
        # Check for PII
        if self.contains_pii(content):
            return FilterResult(allowed=False, reason="contains_pii")
        
        return FilterResult(allowed=True)
```

### 2. Response Validation

Validate AI responses before returning to users:

```python
async def validate_ai_response(response: str) -> bool:
    # Check response quality
    if len(response.strip()) < 10:
        return False
    
    # Check for coherence
    if not self.is_coherent_response(response):
        return False
    
    # Check for safety
    filter_result = await self.content_filter.filter_content(response)
    return filter_result.allowed
```

### 3. Bias Detection and Mitigation

Monitor for bias in AI outputs:

```python
class BiasDetector:
    async def detect_bias(self, prompt: str, response: str) -> BiasReport:
        # Analyze response for potential bias
        bias_indicators = self.analyze_bias_indicators(response)
        
        return BiasReport(
            has_bias=len(bias_indicators) > 0,
            indicators=bias_indicators,
            confidence=self.calculate_confidence(bias_indicators)
        )
```

## Performance Optimization

### 1. Caching AI Results

Cache expensive AI operations:

```python
@lru_cache(maxsize=1000)
async def cached_embedding_generation(content_hash: str) -> List[float]:
    # Generate embeddings only if not cached
    return await ai_service.generate_embeddings([content])

# Use Redis for persistent caching
async def get_cached_summary(content_id: str) -> Optional[str]:
    cache_key = f"summary:{content_id}"
    return await redis_client.get(cache_key)
```

### 2. Batch Processing

Process multiple items together for efficiency:

```python
async def batch_process_embeddings(content_items: List[ContentItem]):
    # Process in batches for better performance
    batch_size = 10
    
    for i in range(0, len(content_items), batch_size):
        batch = content_items[i:i + batch_size]
        texts = [item.content for item in batch]
        
        # Generate embeddings for batch
        embeddings = await ai_service.generate_embeddings(texts)
        
        # Save embeddings
        for item, embedding in zip(batch, embeddings):
            await save_embedding(item.id, embedding)
```

### 3. Async Processing

Use async patterns for concurrent AI operations:

```python
async def process_content_parallel(content_items: List[ContentItem]):
    # Process multiple items concurrently
    tasks = []
    
    for item in content_items:
        task = asyncio.create_task(process_single_item(item))
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle results and exceptions
    for item, result in zip(content_items, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to process {item.id}: {result}")
        else:
            logger.info(f"Successfully processed {item.id}")
```

## Testing AI Components

### 1. Mocking AI Services

Mock AI services for testing:

```python
class MockAIService:
    async def generate_text(self, prompt: str, config: GenerationConfig) -> str:
        # Return predictable responses for testing
        if "summary" in prompt.lower():
            return "This is a test summary."
        return "This is a test response."
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Return mock embeddings
        return [[0.1, 0.2, 0.3] for _ in texts]
```

### 2. Testing AI Workflows

Test complete AI processing workflows:

```python
@pytest.mark.asyncio
async def test_content_ai_processing():
    # Create test content
    content = await create_test_content("Test article content")
    
    # Process with AI
    await process_content_ai(content.id)
    
    # Verify AI processing results
    processed_content = await get_content(content.id)
    assert processed_content.embeddings is not None
    assert processed_content.summary is not None
    assert len(processed_content.entities) > 0
```

### 3. Performance Testing

Test AI component performance:

```python
@pytest.mark.performance
async def test_embedding_generation_performance():
    texts = ["Test text"] * 100
    
    start_time = time.time()
    embeddings = await ai_service.generate_embeddings(texts)
    duration = time.time() - start_time
    
    # Assert performance requirements
    assert duration < 10.0  # Should complete within 10 seconds
    assert len(embeddings) == 100
```