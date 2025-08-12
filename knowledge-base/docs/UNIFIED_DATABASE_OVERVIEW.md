Unified Database Overview (Current State and Modernization Opportunities)

1. Purpose and Scope

This document describes the current unified database schema used by the AI Agent program, how data flows into/through it, the storage format of key fields, and how the frontend consumes the data. The final section outlines modernization opportunities aligned with current best practices.

2. Primary Entities (current state)

2.1 UnifiedTweet (single source of truth)

- Table: unified_tweet
- Purpose: Represents a single Twitter item (or thread root) across the entire pipeline, from caching to knowledge base item generation.
- Key fields
  - Identity and state
    - id (int, PK)
    - tweet_id (str, unique, indexed)
    - bookmarked_tweet_id (str, optional)
  - Processing flags (boolean)
    - urls_expanded, cache_complete, media_processed, categories_processed, kb_item_created, processing_complete
  - Content (mixed types)
    - raw_tweet_data (JSON): original or normalized tweet object
    - thread_tweets (JSON): list of tweets in thread
    - is_thread (bool)
    - full_text (Text): extracted/cleaned text
    - urls_expanded_data (JSON): resolved URL metadata
    - media_files (JSON): list of downloaded media paths (relative, e.g., data/media_cache/...)
    - image_descriptions (JSON): AI-generated captions
  - Categorization
    - main_category (str), sub_category (str)
    - categories_raw_response (JSON): full LLM response for categorization provenance
  - Knowledge Base data (canonical)
    - kb_title (Text), kb_display_title (Text)
    - kb_description (Text)
    - kb_content (Text): legacy markdown storage
    - kb_item_name (Text): derived filename suggestion
    - kb_file_path (Text): legacy disk path for generated README
    - kb_media_paths (JSON): relative paths to media assets
  - Unified fields (new)
    - display_title (Text): preferred display title
    - description (Text): preferred short description
    - markdown_content (Text): canonical markdown content for the KB item
    - raw_json_content (Text): JSON string for enriched, structured content if needed
  - Metadata and tracing
    - source (str: twitter), source_url (Text)
    - processing_errors (JSON), retry_count, last_error, kbitem_error, llm_error
    - force_reprocess_pipeline, force_recache, reprocess_requested_at/by
  - Timestamps
    - created_at, updated_at, cached_at, processed_at, kb_generated_at

Notes
- JSON columns are declared with SQLAlchemy JSON. On PostgreSQL, prefer JSONB for indexing and performance (see recommendations).
- Canonical content SHOULD be markdown_content. HTML should be derived at request/response boundaries, not persisted (see modernization section).

Note (implemented): Server-side render cache (`render_cache` table) stores ephemeral HTML keyed by `(document_type, document_id, content_hash)` for performance. HTML is not canonical; cache can be cleared safely.

2.2 SubcategorySynthesis

- Table: subcategory_synthesis
- Purpose: Stores synthesis documents produced from KB items under a category/sub-category.
- Key fields
  - id (int, PK)
  - main_category (str), sub_category (str)
  - synthesis_title (str), synthesis_short_name (str)
  - synthesis_content (Text): markdown content
  - raw_json_content (Text): optional JSON string for richer structure
  - item_count (int)
  - file_path (str): legacy disk path
  - created_at, last_updated
  - content_hash (str), is_stale (bool), last_item_update (datetime)
  - needs_regeneration (bool)
  - dependency_item_ids (Text JSON array)

2.3 Embedding

- Table: embedding
- Purpose: Vector storage for semantic search (by document and type).
- Key fields
  - id (int, PK)
  - document_id (int), document_type (str: 'kb_item' | 'synthesis')
  - embedding (LargeBinary)
  - model (str)
  - created_at (datetime)
  - Index: (document_type, document_id)

2.4 CategoryHierarchy (metadata)

- Table: category_hierarchy
- Fields: main_category, sub_category, display_name, description, sort_order, is_active, item_count, last_updated
- Constraint: unique (main_category, sub_category)

2.5 Task/Run telemetry (selected)

- CeleryTaskState, TaskLog, JobHistory, RuntimeStatistics
- Purpose: Operational tracking for tasks, phases, metrics, logs

3. Data Flow (high-level)

1) Fetch bookmarks/tweets → raw_tweet_data, thread_tweets, media_files → cache_complete
2) Media processing → media_processed + image_descriptions
3) LLM categorization → main_category, sub_category, categories_raw_response → categories_processed
4) KB generation → markdown_content (canonical), display_title, description, kb_media_paths → kb_item_created
5) Optional synthesis generation → subcategory_synthesis
6) Embeddings optional → embedding

4. Frontend Consumption (current)

- Knowledge Base Page
  - List: `/api/items` returns array of UnifiedTweet-derived items. Fields used include title/display_title, (markdown) content or short preview, categories, timestamps, kb_media_paths.
  - Detail: `/api/items/{id}` returns full markdown_content and derived content_html (rendered on server or client). Media rendered via `/api/media/{path}`. UI prefers HTML if provided, else markdown.

- Synthesis Page
  - List: `/api/synthesis` or `/api/syntheses` returns synthesis documents.
  - Detail: `/api/synthesis/{id}` returns content as markdown or HTML for display.

5. Storage Formats (current)

- Canonical content: markdown (Text) in UnifiedTweet.markdown_content and SubcategorySynthesis.synthesis_content.
- Structured extras: raw_json_content (Text JSON string) for richer sections (key findings, patterns, etc.).
- Media references: JSON arrays of relative paths in kb_media_paths/media_files.
- Metadata: strings/booleans/datetimes as per model.

6. Modernization Opportunities

6.1 Canonical content and rendering
- Only store canonical markdown in unified DB (UnifiedTweet.markdown_content, SubcategorySynthesis.synthesis_content).
- Do not persist HTML. Generate HTML at response time on the server (using cached render) or on the client with a secure markdown renderer and sanitizer.
- Add a server-side cache for rendered HTML keyed by (doc_id, content_hash) to avoid repeated work.

6.2 JSON storage and indexing
- Switch JSON columns to PostgreSQL JSONB for UnifiedTweet JSON fields (raw_tweet_data, thread_tweets, urls_expanded_data, media_files, image_descriptions, categories_raw_response, kb_media_paths, processing_errors).
- Add GIN indexes where appropriate (e.g., on categories, media_files) for analytics/filters.

6.3 Full-text search
- Add TSVECTOR generated columns and GIN index for UnifiedTweet (title/display_title, description, markdown_content) and SubcategorySynthesis (synthesis_title, synthesis_content).
- Expose search endpoints that use PostgreSQL full-text search (with ranking).

6.4 Integrity and constraints
- Ensure unique (main_category, sub_category) maintained in SubcategorySynthesis.
- Consider FK from Embedding.document_id to either UnifiedTweet.id or SubcategorySynthesis.id with a discrete table per doc type (or a strict polymorphic association).
- Enforce not-null for core fields after migration (e.g., markdown_content once legacy kb_content fully retired).
 - Add `render_cache` table (document_type, document_id, content_hash, html) with unique constraint for server-side render caching.

6.5 Legacy removal
- Drop legacy KnowledgeBaseItem and TweetCache references from APIs after migration completion.
- Remove `kb_file_path` usage in favor of DB-only rendering.

6.6 Observability
- Record content_hash for UnifiedTweet.markdown_content to detect drift and drive cache invalidation for rendered HTML.
- Add event/audit logging when content changes (e.g., reprocess, regenerate synthesis, update categorization).

6.7 API consistency and client contracts
- Standardize item detail payload to:
  - id, title, display_title, description, main_category, sub_category, markdown_content, content_html (optional), kb_media_paths, timestamps, source/source_url
- Avoid server returning partially populated structures; all clients should depend on a consistent contract.

7. Proposed “golden path” for KB item rendering

1) GET /api/items (list) → minimal fields for listing (title, categories, last_updated, short preview)
2) On click, GET /api/items/{id} → markdown_content, content_html (optional), media arrays
3) Client renders markdown_content with a sanctioned renderer if content_html is absent; sanitize HTML in either path
4) Media is always rendered from relative paths via `/api/media/{path}`
5) No HTML stored in DB; any HTML seen by the client is ephemeral and generated per request

8. Open Items / Next Steps

- Validate all UnifiedTweet rows have markdown_content populated; fill gaps from legacy kb_content where missing.
- Introduce JSONB types and indexes via a migration.
- Implement server-side render cache (content_hash key) to speed up large documents.
- Finalize removal of legacy endpoints and models once migration is complete.


