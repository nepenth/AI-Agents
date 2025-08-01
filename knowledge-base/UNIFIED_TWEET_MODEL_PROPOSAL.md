# Unified Tweet Model Architecture Proposal

## Problem Statement

The current dual-table architecture (`TweetCache` + `KnowledgeBaseItem`) creates:
- Data duplication and sync complexity
- Inconsistent JSON handling (JSON vs Text columns)
- Multiple sources of truth for the same data
- Unnecessary database sync operations

## Proposed Solution: Single Unified Model

### UnifiedTweet Model

```python
class UnifiedTweet(db.Model):
    """
    Unified Tweet Model - Single source of truth for entire pipeline
    
    Handles the complete lifecycle from initial tweet fetch through 
    knowledge base item generation, using consistent JSON storage.
    """
    __tablename__ = 'unified_tweet'
    
    # === PRIMARY IDENTIFICATION ===
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    bookmarked_tweet_id = db.Column(db.String(50), nullable=False)
    
    # === PIPELINE PROCESSING FLAGS ===
    # Phase 1: Tweet Caching
    urls_expanded = db.Column(db.Boolean, default=False)
    cache_complete = db.Column(db.Boolean, default=False)
    
    # Phase 2: Media Processing  
    media_processed = db.Column(db.Boolean, default=False)
    
    # Phase 3: LLM Processing & Categorization
    categories_processed = db.Column(db.Boolean, default=False)
    
    # Phase 4: Knowledge Base Item Generation
    kb_item_created = db.Column(db.Boolean, default=False)
    kb_item_written_to_disk = db.Column(db.Boolean, default=False)
    
    # Phase 5: Final Processing
    processing_complete = db.Column(db.Boolean, default=False)
    
    # === CONTENT DATA (ALL JSON) ===
    # Raw tweet data
    raw_tweet_data = db.Column(JSON, nullable=True)  # Original tweet JSON from API
    thread_tweets = db.Column(JSON, default=list)    # Thread data if applicable
    
    # Processed content
    full_text = db.Column(db.Text, nullable=True)    # Extracted/cleaned text
    urls_expanded_data = db.Column(JSON, default=list)  # Expanded URL data
    
    # Media data
    media_files = db.Column(JSON, default=list)      # Downloaded media file paths
    image_descriptions = db.Column(JSON, default=list)  # AI-generated descriptions
    
    # === CATEGORIZATION DATA (ALL JSON) ===
    # LLM-generated categorization
    main_category = db.Column(db.String(100), nullable=True)
    sub_category = db.Column(db.String(100), nullable=True)
    categories_raw_response = db.Column(JSON, nullable=True)  # Full LLM response
    
    # === KNOWLEDGE BASE DATA (ALL JSON) ===
    # Generated KB item content
    kb_title = db.Column(db.Text, nullable=True)
    kb_display_title = db.Column(db.Text, nullable=True)
    kb_description = db.Column(db.Text, nullable=True)
    kb_content = db.Column(db.Text, nullable=True)      # Final markdown content
    kb_item_name = db.Column(db.Text, nullable=True)    # Suggested filename
    
    # KB file system data
    kb_file_path = db.Column(db.Text, nullable=True)    # Path to generated README.md
    kb_media_paths = db.Column(JSON, default=list)      # Relative media paths
    
    # === METADATA ===
    source = db.Column(db.String(50), default='twitter')
    source_url = db.Column(db.Text, nullable=True)
    
    # === ERROR TRACKING ===
    processing_errors = db.Column(JSON, default=dict)   # Phase-specific errors
    retry_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text, nullable=True)
    
    # === REPROCESSING CONTROLS ===
    force_reprocess_pipeline = db.Column(db.Boolean, default=False)
    force_recache = db.Column(db.Boolean, default=False)
    reprocess_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reprocess_requested_by = db.Column(db.String(100), nullable=True)
    recategorization_attempts = db.Column(db.Integer, default=0)
    
    # === TIMESTAMPS ===
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    cached_at = db.Column(db.DateTime(timezone=True), nullable=True)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    kb_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # === COMPUTED PROPERTIES ===
    @hybrid_property
    def is_ready_for_media_processing(self):
        return self.cache_complete and not self.media_processed
    
    @hybrid_property
    def is_ready_for_categorization(self):
        return self.media_processed and not self.categories_processed
    
    @hybrid_property
    def is_ready_for_kb_generation(self):
        return self.categories_processed and not self.kb_item_created
    
    @hybrid_property
    def needs_reprocessing(self):
        return self.force_reprocess_pipeline or self.force_recache
    
    def __repr__(self):
        return f'<UnifiedTweet {self.tweet_id} [{self.main_category}/{self.sub_category}]>'
```

## Benefits of Unified Architecture

### 1. Single Source of Truth
- All tweet data in one place
- No sync operations needed
- Consistent data model throughout pipeline

### 2. Consistent JSON Storage
- All complex data stored as JSON columns
- No mixing of JSON and Text for same data types
- Proper database-native JSON support

### 3. Clear Processing Pipeline
- Boolean flags for each processing phase
- Easy to query tweets by processing state
- Clear progression through pipeline stages

### 4. Simplified Queries
```python
# Get tweets ready for media processing
tweets_for_media = UnifiedTweet.query.filter_by(
    cache_complete=True, 
    media_processed=False
).all()

# Get completed KB items
completed_items = UnifiedTweet.query.filter_by(
    processing_complete=True
).all()

# Get tweets that need reprocessing
reprocess_tweets = UnifiedTweet.query.filter(
    UnifiedTweet.force_reprocess_pipeline == True
).all()
```

### 5. Better Error Handling
- Phase-specific error tracking in JSON
- Retry logic built into the model
- Clear error state management

## Migration Strategy

### Phase 1: Create New Model
1. Add `UnifiedTweet` model alongside existing models
2. Create migration script to populate from existing data
3. Update pipeline to write to both old and new models

### Phase 2: Update Pipeline Logic
1. Modify each processing phase to work with unified model
2. Update state management to use unified model
3. Test pipeline end-to-end with new model

### Phase 3: Remove Old Models
1. Update all queries to use unified model
2. Remove sync operations between models
3. Drop old `TweetCache` and `KnowledgeBaseItem` tables

## Code Changes Required

### 1. Models
- Add `UnifiedTweet` model
- Keep existing models during transition

### 2. State Manager
- Update to work with unified model processing flags
- Simplify validation logic (no sync needed)

### 3. Content Processor
- Remove database sync operations
- Update in-place on unified model

### 4. API Endpoints
- Update to query unified model
- Simplify response formatting

### 5. Frontend
- Update to work with unified model structure
- Simplify data handling (single source)

## Example Usage

```python
# Create new tweet entry
tweet = UnifiedTweet(
    tweet_id="123456789",
    bookmarked_tweet_id="123456789",
    raw_tweet_data=tweet_json_from_api
)
db.session.add(tweet)
db.session.commit()

# Update through pipeline phases
# Phase 1: Caching
tweet.full_text = extracted_text
tweet.thread_tweets = thread_data
tweet.cache_complete = True

# Phase 2: Media
tweet.media_files = downloaded_files
tweet.image_descriptions = ai_descriptions
tweet.media_processed = True

# Phase 3: Categorization
tweet.main_category = "AI"
tweet.sub_category = "Machine Learning"
tweet.categories_raw_response = llm_response
tweet.categories_processed = True

# Phase 4: KB Generation
tweet.kb_content = generated_markdown
tweet.kb_file_path = file_path
tweet.kb_media_paths = media_paths
tweet.kb_item_created = True

# Phase 5: Completion
tweet.processing_complete = True
tweet.processed_at = datetime.utcnow()

# Single commit for all updates
db.session.commit()
```

This unified approach eliminates the complexity you identified and provides a much cleaner, more maintainable architecture.