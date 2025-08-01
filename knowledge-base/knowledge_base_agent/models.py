from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from sqlalchemy import Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.ext.hybrid import hybrid_property
import json

db = SQLAlchemy()

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255))

    def __init__(self, key, value):
        self.key = key
        self.value = value

class KnowledgeBaseItem(db.Model):
    __tablename__ = 'knowledge_base_item'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), unique=True, nullable=True)
    title = db.Column(db.String(200), nullable=False)
    display_title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=False)
    main_category = db.Column(db.String(100), nullable=False, default='Uncategorized')
    sub_category = db.Column(db.String(100), nullable=False, default='Uncategorized')
    item_name = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    file_path = db.Column(db.String(500), nullable=True)
    kb_media_paths = db.Column(db.Text, nullable=True)  # JSON string of media paths
    raw_json_content = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<KnowledgeBaseItem {self.title}>'

class SubcategorySynthesis(db.Model):
    __tablename__ = 'subcategory_synthesis'
    
    id = db.Column(db.Integer, primary_key=True)
    main_category = db.Column(db.String(100), nullable=False)
    sub_category = db.Column(db.String(100), nullable=True)
    synthesis_title = db.Column(db.String(255), nullable=False)
    synthesis_short_name = db.Column(db.String(255), nullable=True)
    synthesis_content = db.Column(db.Text, nullable=False)
    raw_json_content = db.Column(db.Text, nullable=True)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    file_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    
    # New fields for dependency tracking
    content_hash = db.Column(db.String(64), nullable=True)  # SHA256 hash of source content
    is_stale = db.Column(db.Boolean, nullable=False, default=False)  # Whether synthesis is out of date
    last_item_update = db.Column(db.DateTime, nullable=True)  # Latest update time from source KB items
    needs_regeneration = db.Column(db.Boolean, nullable=False, default=False)  # Explicitly marked for regen
    dependency_item_ids = db.Column(db.Text, nullable=True)  # JSON array of KB item IDs this synthesis depends on
    
    __table_args__ = (
        db.UniqueConstraint('main_category', 'sub_category', name='uq_main_sub_category'),
    )

    def __repr__(self):
        return f'<SubcategorySynthesis {self.main_category}/{self.sub_category}>'

    def __init__(self, main_category, sub_category, synthesis_title, synthesis_content, item_count, created_at, last_updated, file_path=None, raw_json_content=None, synthesis_short_name=None):
        self.main_category = main_category
        self.sub_category = sub_category
        self.synthesis_title = synthesis_title
        self.synthesis_content = synthesis_content
        self.item_count = item_count
        self.created_at = created_at
        self.last_updated = last_updated
        self.file_path = file_path
        self.raw_json_content = raw_json_content
        self.synthesis_short_name = synthesis_short_name


class TaskLog(db.Model):
    """Stores individual log entries for agent task executions."""
    __tablename__ = 'task_log'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey('celery_task_state.task_id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    level = db.Column(db.String(10), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = db.Column(db.Text, nullable=False)
    component = db.Column(db.String(100), nullable=True, index=True)  # e.g., 'content_processor', 'agent'
    phase = db.Column(db.String(50), nullable=True, index=True)  # e.g., 'tweet_caching', 'llm_processing'
    
    # Structured data fields
    log_metadata = db.Column(db.Text, nullable=True)  # JSON for additional structured data
    progress_data = db.Column(db.Text, nullable=True)  # JSON for progress information
    error_data = db.Column(db.Text, nullable=True)  # JSON for error context and tracebacks
    
    # Performance and filtering
    sequence_number = db.Column(db.Integer, nullable=False)  # Sequential number within task
    
    # Relationships
    task = db.relationship('CeleryTaskState', backref=db.backref('logs', lazy='dynamic', cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<TaskLog {self.task_id}:{self.sequence_number} [{self.level}] {self.message[:50]}...>'
    
    def to_dict(self):
        """Convert log entry to dictionary for API responses."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'component': self.component,
            'phase': self.phase,
            'sequence_number': self.sequence_number,
            'metadata': json.loads(self.log_metadata) if self.log_metadata else None,
            'progress_data': json.loads(self.progress_data) if self.progress_data else None,
            'error_data': json.loads(self.error_data) if self.error_data else None
        }


class AgentState(db.Model):
    """A singleton table to store the operational state of the agent."""
    __tablename__ = 'agent_state'
    
    id = db.Column(db.Integer, primary_key=True)
    is_running = db.Column(db.Boolean, nullable=False, default=False)
    current_run_preferences = db.Column(db.Text, nullable=True) # Stored as JSON
    plan_statuses = db.Column(db.Text, nullable=True) # Stored as JSON
    phase_estimates = db.Column(db.Text, nullable=True) # Stored as JSON
    current_phase_id = db.Column(db.String(100), nullable=True)
    current_phase_message = db.Column(db.String(500), nullable=True)
    current_phase_status = db.Column(db.String(50), nullable=True)
    stop_flag_status = db.Column(db.Boolean, nullable=False, default=False)
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # --- Celery Integration Fields ---
    # Links to the currently active Celery task running the agent
    current_task_id = db.Column(db.String(36), db.ForeignKey('celery_task_state.task_id'), nullable=True)
    # Estimated number of tasks in the queue (can be updated periodically)
    task_queue_size = db.Column(db.Integer, default=0)
    
    # Relationship to the current task
    current_task = db.relationship('CeleryTaskState', foreign_keys=[current_task_id])

    def __init__(self, is_running=False, current_phase_message="Idle", last_update=None, **kwargs):
        self.is_running = is_running
        self.current_phase_message = current_phase_message
        self.last_update = last_update or datetime.utcnow()
        # Allows other fields to be set via kwargs if needed, or defaults to None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        import json
        try:
            prefs = json.loads(self.current_run_preferences) if self.current_run_preferences else None
        except (json.JSONDecodeError, TypeError):
            prefs = {}
        try:
            plan = json.loads(self.plan_statuses) if self.plan_statuses else {}
        except (json.JSONDecodeError, TypeError):
            plan = {}
        try:
            estimates = json.loads(self.phase_estimates) if self.phase_estimates else {}
        except (json.JSONDecodeError, TypeError):
            estimates = {}

        return {
            'is_running': self.is_running,
            'current_run_preferences': prefs,
            'plan_statuses': plan,
            'phase_estimates': estimates,
            'current_phase_id': self.current_phase_id,
            'current_phase_message': self.current_phase_message,
            'current_phase_status': self.current_phase_status,
            'stop_flag_status': self.stop_flag_status,
            'last_update': self.last_update.isoformat()
        }

class CeleryTaskState(db.Model):
    """
    Enhanced task state management for complete lifecycle tracking.
    Supports both active task monitoring and historical job records.
    """
    __tablename__ = 'celery_task_state'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), unique=True, nullable=False, index=True)  # Custom-generated UUID
    celery_task_id = db.Column(db.String(36), nullable=True, index=True) # Celery's internal task ID
    task_type = db.Column(db.String(100), nullable=False, index=True)  # e.g., 'agent_run', 'fetch_bookmarks', 'git_sync'
    status = db.Column(db.String(20), nullable=False, default='PENDING', index=True)  # PENDING, PROGRESS, SUCCESS, FAILURE, REVOKED
    
    # Progress tracking fields
    current_phase_id = db.Column(db.String(50), nullable=True)
    current_phase_message = db.Column(db.Text, nullable=True)
    progress_percentage = db.Column(db.Integer, default=0)
    
    # Enhanced task metadata
    human_readable_name = db.Column(db.String(200), nullable=True)  # Human-readable task name with timestamp
    preferences = db.Column(db.JSON, nullable=True)  # Store UserPreferences as JSON for agent runs
    result_data = db.Column(db.JSON, nullable=True)  # Store task final results
    run_report = db.Column(db.JSON, nullable=True)  # Store detailed run report
    error_message = db.Column(db.Text, nullable=True)
    traceback = db.Column(db.Text, nullable=True)
    
    # Execution statistics
    items_processed = db.Column(db.Integer, default=0)
    items_failed = db.Column(db.Integer, default=0)
    execution_duration = db.Column(db.String(50), nullable=True)  # Human-readable duration
    
    # State management flags
    is_active = db.Column(db.Boolean, default=True, index=True)  # Whether this is the current active task
    is_archived = db.Column(db.Boolean, default=False, index=True)  # Whether task is archived
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, task_id, task_type, status, preferences=None, celery_task_id=None, current_phase_id=None, current_phase_message=None, progress_percentage=0, result_data=None, error_message=None, traceback=None, human_readable_name=None, run_report=None, items_processed=0, items_failed=0, execution_duration=None, is_active=True, is_archived=False):
        self.task_id = task_id
        self.task_type = task_type
        self.status = status
        self.preferences = preferences
        self.celery_task_id = celery_task_id
        self.current_phase_id = current_phase_id
        self.current_phase_message = current_phase_message
        self.progress_percentage = progress_percentage
        self.result_data = result_data
        self.error_message = error_message
        self.traceback = traceback
        self.human_readable_name = human_readable_name
        self.run_report = run_report
        self.items_processed = items_processed
        self.items_failed = items_failed
        self.execution_duration = execution_duration
        self.is_active = is_active
        self.is_archived = is_archived
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f'<CeleryTaskState {self.task_id} [{self.task_type}] - {self.status}>'


class Embedding(db.Model):
    __tablename__ = 'embedding'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, nullable=False)
    document_type = db.Column(db.String(50), nullable=False) # 'kb_item' or 'synthesis'
    embedding = db.Column(db.LargeBinary, nullable=False)
    model = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        db.Index('idx_embedding_doc_type_id', 'document_type', 'document_id'),
    )

    def __repr__(self):
        return f'<Embedding for {self.document_type} {self.document_id}>'

class ChatSession(db.Model):
    __tablename__ = 'chat_session'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    message_count = db.Column(db.Integer, nullable=False, default=0)
    
    # Relationship to chat messages
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChatSession {self.session_id}>'

class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey('chat_session.session_id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    model_used = db.Column(db.String(100), nullable=True)
    sources = db.Column(db.Text, nullable=True)  # JSON string of source documents
    context_stats = db.Column(db.Text, nullable=True)  # JSON string of context statistics
    performance_metrics = db.Column(db.Text, nullable=True)  # JSON string of performance data
    
    def __repr__(self):
        return f'<ChatMessage {self.role} in {self.session_id}>'

class Schedule(db.Model):
    __tablename__ = 'schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    frequency = db.Column(db.String(50), nullable=False)  # 'manual', 'daily', 'weekly', 'monthly', 'custom'
    time = db.Column(db.String(10), nullable=True)  # HH:MM format
    day_of_week = db.Column(db.Integer, nullable=True)  # 0-6 (Sunday-Saturday)
    day_of_month = db.Column(db.Integer, nullable=True)  # 1-31
    cron_expression = db.Column(db.String(100), nullable=True)  # For custom schedules
    pipeline_type = db.Column(db.String(50), nullable=False, default='full')
    pipeline_config = db.Column(db.Text, nullable=True)  # JSON string of pipeline configuration
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    next_run = db.Column(db.DateTime, nullable=True)
    last_run = db.Column(db.DateTime, nullable=True)
    
    # Relationship to schedule runs
    runs = db.relationship('ScheduleRun', backref='schedule', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Schedule {self.name}>'

class ScheduleRun(db.Model):
    __tablename__ = 'schedule_run'
    
    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)
    execution_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'running', 'completed', 'failed'
    duration = db.Column(db.String(50), nullable=True)
    processed_items = db.Column(db.Integer, nullable=True, default=0)
    error_message = db.Column(db.Text, nullable=True)
    logs = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<ScheduleRun {self.id} for schedule {self.schedule_id}>'


class JobHistory(db.Model):
    """
    Comprehensive job history tracking for all agent executions.
    Provides historical view of all runs with detailed metadata.
    """
    __tablename__ = 'job_history'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey('celery_task_state.task_id'), nullable=False, index=True)
    job_type = db.Column(db.String(50), nullable=False, index=True)  # 'manual', 'scheduled', 'api'
    trigger_source = db.Column(db.String(100), nullable=True)  # 'web_ui', 'api_call', 'schedule_name'
    
    # Execution summary
    execution_summary = db.Column(db.JSON, nullable=True)  # Summary of what was processed
    phase_results = db.Column(db.JSON, nullable=True)  # Results from each processing phase
    performance_metrics = db.Column(db.JSON, nullable=True)  # Performance statistics
    
    # User context
    user_preferences = db.Column(db.JSON, nullable=True)  # Snapshot of preferences used
    system_info = db.Column(db.JSON, nullable=True)  # System state at execution time
    
    # Categorization
    tags = db.Column(db.JSON, nullable=True)  # User-defined tags for organization
    notes = db.Column(db.Text, nullable=True)  # User notes about this run
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    task = db.relationship('CeleryTaskState', backref=db.backref('history', uselist=False, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<JobHistory {self.task_id} [{self.job_type}]>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'job_type': self.job_type,
            'trigger_source': self.trigger_source,
            'execution_summary': self.execution_summary,
            'phase_results': self.phase_results,
            'performance_metrics': self.performance_metrics,
            'user_preferences': self.user_preferences,
            'system_info': self.system_info,
            'tags': self.tags,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'task': {
                'status': self.task.status,
                'human_readable_name': self.task.human_readable_name,
                'started_at': self.task.started_at.isoformat() if self.task.started_at else None,
                'completed_at': self.task.completed_at.isoformat() if self.task.completed_at else None,
                'execution_duration': self.task.execution_duration,
                'items_processed': self.task.items_processed,
                'items_failed': self.task.items_failed
            } if self.task else None
        }


# ===== UNIFIED TWEET MODEL - SINGLE SOURCE OF TRUTH =====

class UnifiedTweet(db.Model):
    """
    Unified Tweet Model - Single source of truth for entire pipeline
    
    Handles the complete lifecycle from initial tweet fetch through 
    knowledge base item generation, using consistent JSON storage.
    
    This model replaces both TweetCache and KnowledgeBaseItem to eliminate
    data duplication and sync complexity.
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
    is_thread = db.Column(db.Boolean, default=False)
    
    # Processed content
    full_text = db.Column(db.Text, nullable=True)    # Extracted/cleaned text
    urls_expanded_data = db.Column(JSON, default=list)  # Expanded URL data
    
    # Media data
    media_files = db.Column(JSON, default=list)      # Downloaded media file paths (replaces all_downloaded_media_for_thread)
    image_descriptions = db.Column(JSON, default=list)  # AI-generated descriptions
    
    # === CATEGORIZATION DATA (ALL JSON) ===
    # LLM-generated categorization
    main_category = db.Column(db.String(100), nullable=True)
    sub_category = db.Column(db.String(100), nullable=True)
    categories_raw_response = db.Column(JSON, nullable=True)  # Full LLM response (replaces categories field)
    
    # === KNOWLEDGE BASE DATA (ALL JSON) ===
    # Generated KB item content
    kb_title = db.Column(db.Text, nullable=True)
    kb_display_title = db.Column(db.Text, nullable=True)
    kb_description = db.Column(db.Text, nullable=True)
    kb_content = db.Column(db.Text, nullable=True)      # Final markdown content
    kb_item_name = db.Column(db.Text, nullable=True)    # Suggested filename (replaces item_name_suggestion)
    
    # KB file system data
    kb_file_path = db.Column(db.Text, nullable=True)    # Path to generated README.md (replaces kb_item_path)
    kb_media_paths = db.Column(JSON, default=list)      # Relative media paths
    
    # === METADATA ===
    source = db.Column(db.String(50), default='twitter')
    source_url = db.Column(db.Text, nullable=True)
    
    # === ERROR TRACKING ===
    processing_errors = db.Column(JSON, default=dict)   # Phase-specific errors
    retry_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text, nullable=True)
    kbitem_error = db.Column(db.Text, nullable=True)    # Preserve existing error field
    llm_error = db.Column(db.Text, nullable=True)       # Preserve existing error field
    
    # === REPROCESSING CONTROLS ===
    force_reprocess_pipeline = db.Column(db.Boolean, default=False)
    force_recache = db.Column(db.Boolean, default=False)
    reprocess_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reprocess_requested_by = db.Column(db.String(100), nullable=True)
    recategorization_attempts = db.Column(db.Integer, default=0)
    
    # === RUNTIME FLAGS (for backward compatibility) ===
    cache_succeeded_this_run = db.Column(db.Boolean, default=False)
    media_succeeded_this_run = db.Column(db.Boolean, default=False)
    llm_succeeded_this_run = db.Column(db.Boolean, default=False)
    kbitem_succeeded_this_run = db.Column(db.Boolean, default=False)
    db_synced = db.Column(db.Boolean, default=True)  # Always true for unified model
    
    # === TIMESTAMPS ===
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    cached_at = db.Column(db.DateTime(timezone=True), nullable=True)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    kb_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # === COMPUTED PROPERTIES ===
    @hybrid_property
    def is_ready_for_media_processing(self):
        """Check if tweet is ready for media processing phase."""
        return self.cache_complete and not self.media_processed
    
    @hybrid_property
    def is_ready_for_categorization(self):
        """Check if tweet is ready for LLM categorization phase."""
        return self.media_processed and not self.categories_processed
    
    @hybrid_property
    def is_ready_for_kb_generation(self):
        """Check if tweet is ready for knowledge base generation phase."""
        return self.categories_processed and not self.kb_item_created
    
    @hybrid_property
    def needs_reprocessing(self):
        """Check if tweet needs reprocessing."""
        return self.force_reprocess_pipeline or self.force_recache
    
    @hybrid_property
    def pipeline_complete(self):
        """Check if entire pipeline is complete."""
        return (self.cache_complete and 
                self.media_processed and 
                self.categories_processed and 
                self.kb_item_created and
                self.processing_complete)
    
    def to_dict(self, include_content=True):
        """Convert to dictionary for API responses with backward compatibility."""
        data = {
            'id': self.id,
            'tweet_id': self.tweet_id,
            'bookmarked_tweet_id': self.bookmarked_tweet_id,
            'is_thread': self.is_thread,
            'processing_flags': {
                'urls_expanded': self.urls_expanded,
                'media_processed': self.media_processed,
                'cache_complete': self.cache_complete,
                'categories_processed': self.categories_processed,
                'kb_item_created': self.kb_item_created,
                'processing_complete': self.processing_complete,
                'pipeline_complete': self.pipeline_complete
            },
            'reprocessing_controls': {
                'force_reprocess_pipeline': self.force_reprocess_pipeline,
                'force_recache': self.force_recache,
                'reprocess_requested_at': self.reprocess_requested_at.isoformat() if self.reprocess_requested_at else None,
                'reprocess_requested_by': self.reprocess_requested_by,
                'needs_reprocessing': self.needs_reprocessing
            },
            'categorization': {
                'main_category': self.main_category,
                'sub_category': self.sub_category,
                'kb_item_name': self.kb_item_name,
                'categories_raw_response': self.categories_raw_response
            },
            'knowledge_base': {
                'kb_title': self.kb_title,
                'kb_display_title': self.kb_display_title,
                'kb_file_path': self.kb_file_path,
                'kb_media_paths': self.kb_media_paths,
                'kb_content': self.kb_content if include_content else None
            },
            'metadata': {
                'source': self.source,
                'source_url': self.source_url,
                'recategorization_attempts': self.recategorization_attempts,
                'retry_count': self.retry_count
            },
            'timestamps': {
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'cached_at': self.cached_at.isoformat() if self.cached_at else None,
                'processed_at': self.processed_at.isoformat() if self.processed_at else None,
                'kb_generated_at': self.kb_generated_at.isoformat() if self.kb_generated_at else None
            }
        }
        
        if include_content:
            data.update({
                'content': {
                    'raw_tweet_data': self.raw_tweet_data,
                    'thread_tweets': self.thread_tweets,
                    'full_text': self.full_text,
                    'media_files': self.media_files,
                    'image_descriptions': self.image_descriptions,
                    'urls_expanded_data': self.urls_expanded_data
                },
                'errors': {
                    'processing_errors': self.processing_errors,
                    'last_error': self.last_error,
                    'kbitem_error': self.kbitem_error,
                    'llm_error': self.llm_error
                }
            })
        
        return data
    
    def __repr__(self):
        return f'<UnifiedTweet {self.tweet_id} [{self.main_category}/{self.sub_category}]>'


# ===== LEGACY MODELS (DEPRECATED - USE UnifiedTweet INSTEAD) =====
# These models are kept temporarily for migration purposes only.
# All new code should use UnifiedTweet model.

class TweetCache(db.Model):
    """
    Enhanced Tweet Cache Model (replaces tweet_cache.json)
    
    Stores comprehensive tweet data with processing flags, categorization,
    and reprocessing controls for the AI agent pipeline.
    """
    __tablename__ = 'tweet_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    bookmarked_tweet_id = db.Column(db.String(50), nullable=False)
    is_thread = db.Column(db.Boolean, default=False)
    thread_tweets = db.Column(JSON, default=list)
    all_downloaded_media_for_thread = db.Column(JSON, default=list)
    
    # Processing flags
    urls_expanded = db.Column(db.Boolean, default=False)
    media_processed = db.Column(db.Boolean, default=False)
    cache_complete = db.Column(db.Boolean, default=False)
    categories_processed = db.Column(db.Boolean, default=False)
    kb_item_created = db.Column(db.Boolean, default=False)
    
    # Manual reprocessing controls
    force_reprocess_pipeline = db.Column(db.Boolean, default=False)
    force_recache = db.Column(db.Boolean, default=False)
    reprocess_requested_at = db.Column(db.DateTime(timezone=True))
    reprocess_requested_by = db.Column(db.String(100))
    
    # Categorization data
    main_category = db.Column(db.String(100))
    sub_category = db.Column(db.String(100))
    item_name_suggestion = db.Column(db.Text)
    categories = db.Column(JSON, default=dict)
    
    # Knowledge base integration
    kb_item_path = db.Column(db.Text)
    kb_media_paths = db.Column(JSON, default=list)
    
    # Content and metadata
    raw_json_content = db.Column(JSON)
    display_title = db.Column(db.Text)
    source = db.Column(db.String(50), default='unknown')
    image_descriptions = db.Column(JSON, default=list)
    full_text = db.Column(db.Text)  # Extracted text for full-text search
    
    # Processing metadata
    recategorization_attempts = db.Column(db.Integer, default=0)
    
    # Runtime flags (prefixed with _)
    cache_succeeded_this_run = db.Column(db.Boolean, default=False)
    media_succeeded_this_run = db.Column(db.Boolean, default=False)
    llm_succeeded_this_run = db.Column(db.Boolean, default=False)
    kbitem_succeeded_this_run = db.Column(db.Boolean, default=False)
    
    # Error tracking
    kbitem_error = db.Column(db.Text)
    llm_error = db.Column(db.Text)
    
    # Additional fields
    db_synced = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    processing_queue = db.relationship("TweetProcessingQueue", back_populates="tweet", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<TweetCache {self.tweet_id} [{self.main_category}/{self.sub_category}]>'
    
    @hybrid_property
    def processing_complete(self):
        """Check if all processing phases are complete."""
        return (self.cache_complete and 
                self.media_processed and 
                self.categories_processed and 
                self.kb_item_created)
    
    @hybrid_property
    def needs_reprocessing(self):
        """Check if tweet needs reprocessing."""
        return self.force_reprocess_pipeline or self.force_recache
    
    def to_dict(self, include_content=True):
        """Convert to dictionary for API responses."""
        data = {
            'id': self.id,
            'tweet_id': self.tweet_id,
            'bookmarked_tweet_id': self.bookmarked_tweet_id,
            'is_thread': self.is_thread,
            'processing_flags': {
                'urls_expanded': self.urls_expanded,
                'media_processed': self.media_processed,
                'cache_complete': self.cache_complete,
                'categories_processed': self.categories_processed,
                'kb_item_created': self.kb_item_created,
                'processing_complete': self.processing_complete
            },
            'reprocessing_controls': {
                'force_reprocess_pipeline': self.force_reprocess_pipeline,
                'force_recache': self.force_recache,
                'reprocess_requested_at': self.reprocess_requested_at.isoformat() if self.reprocess_requested_at else None,
                'reprocess_requested_by': self.reprocess_requested_by,
                'needs_reprocessing': self.needs_reprocessing
            },
            'categorization': {
                'main_category': self.main_category,
                'sub_category': self.sub_category,
                'item_name_suggestion': self.item_name_suggestion,
                'categories': self.categories
            },
            'metadata': {
                'source': self.source,
                'display_title': self.display_title,
                'recategorization_attempts': self.recategorization_attempts,
                'db_synced': self.db_synced
            },
            'timestamps': {
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None
            }
        }
        
        if include_content:
            data.update({
                'content': {
                    'thread_tweets': self.thread_tweets,
                    'all_downloaded_media_for_thread': self.all_downloaded_media_for_thread,
                    'kb_item_path': self.kb_item_path,
                    'kb_media_paths': self.kb_media_paths,
                    'image_descriptions': self.image_descriptions,
                    'full_text': self.full_text,
                    'raw_json_content': self.raw_json_content
                },
                'errors': {
                    'kbitem_error': self.kbitem_error,
                    'llm_error': self.llm_error
                }
            })
        
        return data


class TweetProcessingQueue(db.Model):
    """
    Processing Queue Model (replaces processed_tweets.json and unprocessed_tweets.json)
    
    Manages tweet processing workflow with status tracking, priority, and retry logic.
    """
    __tablename__ = 'tweet_processing_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), db.ForeignKey('tweet_cache.tweet_id'), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='unprocessed', index=True)  # 'unprocessed', 'processing', 'processed', 'failed'
    processing_phase = db.Column(db.String(50), index=True)  # 'cache', 'media', 'categorization', 'kb_item', 'db_sync'
    priority = db.Column(db.Integer, default=0, index=True)
    retry_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at = db.Column(db.DateTime(timezone=True))
    
    # Relationships
    tweet = db.relationship("TweetCache", back_populates="processing_queue")
    
    def __repr__(self):
        return f'<TweetProcessingQueue {self.tweet_id} [{self.status}] - {self.processing_phase}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'tweet_id': self.tweet_id,
            'status': self.status,
            'processing_phase': self.processing_phase,
            'priority': self.priority,
            'retry_count': self.retry_count,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }


class CategoryHierarchy(db.Model):
    """
    Category Hierarchy Model (replaces categories.json)
    
    Manages hierarchical category structure with metadata and item counts.
    """
    __tablename__ = 'category_hierarchy'
    
    id = db.Column(db.Integer, primary_key=True)
    main_category = db.Column(db.String(100), nullable=False, index=True)
    sub_category = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(200))
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Metadata
    item_count = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        db.UniqueConstraint('main_category', 'sub_category', name='uq_category_hierarchy_main_sub'),
    )
    
    def __repr__(self):
        return f'<CategoryHierarchy {self.main_category}/{self.sub_category} ({self.item_count} items)>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'main_category': self.main_category,
            'sub_category': self.sub_category,
            'display_name': self.display_name,
            'description': self.description,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
            'item_count': self.item_count,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


class ProcessingStatistics(db.Model):
    """
    Processing Statistics Model (replaces processing_stats.json)
    
    Stores detailed phase-by-phase processing statistics and metrics.
    """
    __tablename__ = 'processing_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    phase_name = db.Column(db.String(100), nullable=False, index=True)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Numeric)
    metric_unit = db.Column(db.String(50))
    
    # Aggregation data
    total_items_processed = db.Column(db.Integer, default=0)
    total_duration_seconds = db.Column(db.Numeric, default=0)
    avg_time_per_item_seconds = db.Column(db.Numeric, default=0)
    
    # Metadata
    run_id = db.Column(db.String(36), index=True)  # Links to specific agent runs
    recorded_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        db.UniqueConstraint('phase_name', 'metric_name', 'run_id', name='uq_processing_stats_phase_metric_run'),
    )
    
    def __repr__(self):
        return f'<ProcessingStatistics {self.phase_name}.{self.metric_name} = {self.metric_value}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'phase_name': self.phase_name,
            'metric_name': self.metric_name,
            'metric_value': float(self.metric_value) if self.metric_value else None,
            'metric_unit': self.metric_unit,
            'total_items_processed': self.total_items_processed,
            'total_duration_seconds': float(self.total_duration_seconds) if self.total_duration_seconds else None,
            'avg_time_per_item_seconds': float(self.avg_time_per_item_seconds) if self.avg_time_per_item_seconds else None,
            'run_id': self.run_id,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }


class RuntimeStatistics(db.Model):
    """
    Runtime Statistics Model (replaces latest_run_stats.json)
    
    Stores runtime statistics and performance metrics for agent runs.
    """
    __tablename__ = 'runtime_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    
    # Basic counters
    processed_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    skipped_count = db.Column(db.Integer, default=0)
    
    # Media processing
    media_processed = db.Column(db.Integer, default=0)
    
    # Cache statistics
    cache_hits = db.Column(db.Integer, default=0)
    cache_misses = db.Column(db.Integer, default=0)
    
    # Network statistics
    network_errors = db.Column(db.Integer, default=0)
    retry_count = db.Column(db.Integer, default=0)
    
    # Calculated metrics
    success_rate = db.Column(db.Numeric(5, 2))
    cache_hit_rate = db.Column(db.Numeric(5, 2))
    error_rate = db.Column(db.Numeric(5, 2))
    average_retries = db.Column(db.Numeric(10, 2))
    
    # Timing
    start_time = db.Column(db.DateTime(timezone=True))
    end_time = db.Column(db.DateTime(timezone=True))
    duration = db.Column(db.Interval)
    
    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f'<RuntimeStatistics {self.run_id} - {self.processed_count} processed>'
    
    @hybrid_property
    def duration_seconds(self):
        """Get duration in seconds."""
        if self.duration:
            return self.duration.total_seconds()
        return None
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'run_id': self.run_id,
            'counters': {
                'processed_count': self.processed_count,
                'success_count': self.success_count,
                'error_count': self.error_count,
                'skipped_count': self.skipped_count,
                'media_processed': self.media_processed
            },
            'cache_stats': {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses
            },
            'network_stats': {
                'network_errors': self.network_errors,
                'retry_count': self.retry_count
            },
            'calculated_metrics': {
                'success_rate': float(self.success_rate) if self.success_rate else None,
                'cache_hit_rate': float(self.cache_hit_rate) if self.cache_hit_rate else None,
                'error_rate': float(self.error_rate) if self.error_rate else None,
                'average_retries': float(self.average_retries) if self.average_retries else None
            },
            'timing': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration_seconds': self.duration_seconds
            },
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TweetBookmark(db.Model):
    """
    Tweet Bookmark Model (replaces tweet_bookmarks.json)
    
    Stores Twitter bookmark data with fetch timestamps and URL information.
    """
    __tablename__ = 'tweet_bookmarks'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    url_path = db.Column(db.String(500), nullable=False)
    full_url = db.Column(db.String(500), nullable=False)
    
    # Timestamps
    first_fetched_at = db.Column(db.DateTime(timezone=True), nullable=False)
    last_seen_bookmarked_at = db.Column(db.DateTime(timezone=True), nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f'<TweetBookmark {self.tweet_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'tweet_id': self.tweet_id,
            'url_path': self.url_path,
            'full_url': self.full_url,
            'first_fetched_at': self.first_fetched_at.isoformat() if self.first_fetched_at else None,
            'last_seen_bookmarked_at': self.last_seen_bookmarked_at.isoformat() if self.last_seen_bookmarked_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UnifiedTweet(db.Model):
    """
    Unified Tweet Model - Single Source of Truth
    
    Replaces the dual TweetCache + KnowledgeBaseItem architecture with a single
    comprehensive model that tracks all processing states and content.
    """
    __tablename__ = 'unified_tweet'
    __table_args__ = {'extend_existing': True}
    
    # === PRIMARY IDENTIFICATION ===
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    bookmarked_tweet_id = db.Column(db.String(50), nullable=True)
    
    # === PIPELINE PROCESSING FLAGS ===
    urls_expanded = db.Column(db.Boolean, default=False)
    cache_complete = db.Column(db.Boolean, default=False)
    media_processed = db.Column(db.Boolean, default=False)
    categories_processed = db.Column(db.Boolean, default=False)
    kb_item_created = db.Column(db.Boolean, default=False)
    processing_complete = db.Column(db.Boolean, default=False)
    
    # === CONTENT DATA ===
    raw_tweet_data = db.Column(JSON, nullable=True)
    thread_tweets = db.Column(JSON, nullable=True)
    is_thread = db.Column(db.Boolean, default=False)
    full_text = db.Column(db.Text, nullable=True)
    urls_expanded_data = db.Column(JSON, nullable=True)
    media_files = db.Column(JSON, nullable=True)
    image_descriptions = db.Column(JSON, nullable=True)
    
    # === CATEGORIZATION DATA ===
    main_category = db.Column(db.String(100), nullable=True)
    sub_category = db.Column(db.String(100), nullable=True)
    categories_raw_response = db.Column(JSON, nullable=True)
    
    # === KNOWLEDGE BASE DATA ===
    kb_title = db.Column(db.Text, nullable=True)
    kb_display_title = db.Column(db.Text, nullable=True)
    kb_description = db.Column(db.Text, nullable=True)
    kb_content = db.Column(db.Text, nullable=True)
    kb_item_name = db.Column(db.Text, nullable=True)
    kb_file_path = db.Column(db.Text, nullable=True)  # Legacy field for backward compatibility
    kb_media_paths = db.Column(JSON, nullable=True)
    
    # === UNIFIED DB FIELDS (New) ===
    display_title = db.Column(db.Text, nullable=True)  # Unified display title
    description = db.Column(db.Text, nullable=True)    # Unified description
    markdown_content = db.Column(db.Text, nullable=True)  # Full markdown content
    raw_json_content = db.Column(db.Text, nullable=True)  # Raw JSON content
    
    # === METADATA ===
    source = db.Column(db.String(50), default='twitter')
    source_url = db.Column(db.Text, nullable=True)
    
    # === ERROR TRACKING ===
    processing_errors = db.Column(JSON, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text, nullable=True)
    kbitem_error = db.Column(db.Text, nullable=True)
    llm_error = db.Column(db.Text, nullable=True)
    
    # === REPROCESSING CONTROLS ===
    force_reprocess_pipeline = db.Column(db.Boolean, default=False)
    force_recache = db.Column(db.Boolean, default=False)
    reprocess_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reprocess_requested_by = db.Column(db.String(100), nullable=True)
    recategorization_attempts = db.Column(db.Integer, default=0)
    
    # === RUNTIME FLAGS (for current execution tracking) ===
    cache_succeeded_this_run = db.Column(db.Boolean, default=False)
    media_succeeded_this_run = db.Column(db.Boolean, default=False)
    llm_succeeded_this_run = db.Column(db.Boolean, default=False)
    kbitem_succeeded_this_run = db.Column(db.Boolean, default=False)
    
    # === TIMESTAMPS ===
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    cached_at = db.Column(db.DateTime(timezone=True), nullable=True)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    kb_generated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f'<UnifiedTweet {self.tweet_id}>'
    
    def to_dict(self):
        """Convert to dictionary format for backward compatibility."""
        return {
            'id': self.id,
            'tweet_id': self.tweet_id,
            'bookmarked_tweet_id': self.bookmarked_tweet_id,
            
            # Processing flags
            'cache_complete': self.cache_complete,
            'media_processed': self.media_processed,
            'categories_processed': self.categories_processed,
            'kb_item_created': self.kb_item_created,
            'processing_complete': self.processing_complete,
            
            # Content
            'raw_tweet_data': self.raw_tweet_data,
            'thread_tweets': self.thread_tweets,
            'is_thread': self.is_thread,
            'full_text': self.full_text,
            'media_files': self.media_files,
            'image_descriptions': self.image_descriptions,
            
            # Categorization
            'main_category': self.main_category,
            'sub_category': self.sub_category,
            'categories': {
                'main_category': self.main_category,
                'sub_category': self.sub_category,
                'item_name': self.kb_item_name
            } if self.main_category else None,
            
            # Knowledge Base (unified fields)
            'title': self.display_title or self.kb_title,
            'display_title': self.display_title,
            'description': self.description,
            'content': self.markdown_content or self.kb_content,
            'markdown_content': self.markdown_content,
            'raw_json_content': self.raw_json_content,
            'kb_media_paths': self.kb_media_paths,
            'item_name_suggestion': self.kb_item_name,
            
            # Metadata
            'source': self.source,
            'source_url': self.source_url,
            
            # Error tracking
            'kbitem_error': self.kbitem_error,
            'llm_error': self.llm_error,
            'retry_count': self.retry_count,
            
            # Timestamps
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'cached_at': self.cached_at.isoformat() if self.cached_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'last_updated': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def create_from_tweet_data(cls, tweet_id: str, tweet_data: dict):
        """Create a new UnifiedTweet from tweet data dictionary."""
        unified_tweet = cls(
            tweet_id=tweet_id,
            bookmarked_tweet_id=tweet_data.get('bookmarked_tweet_id'),
            
            # Processing flags
            cache_complete=tweet_data.get('cache_complete', False),
            media_processed=tweet_data.get('media_processed', False),
            categories_processed=tweet_data.get('categories_processed', False),
            kb_item_created=tweet_data.get('kb_item_created', False),
            processing_complete=tweet_data.get('processing_complete', False),
            
            # Content
            raw_tweet_data=tweet_data.get('raw_tweet_data'),
            thread_tweets=tweet_data.get('thread_tweets'),
            is_thread=tweet_data.get('is_thread', False),
            full_text=tweet_data.get('full_text'),
            media_files=tweet_data.get('media_files'),
            image_descriptions=tweet_data.get('image_descriptions'),
            
            # Categorization
            main_category=tweet_data.get('main_category'),
            sub_category=tweet_data.get('sub_category'),
            kb_item_name=tweet_data.get('item_name_suggestion'),
            
            # Knowledge Base
            display_title=tweet_data.get('display_title'),
            description=tweet_data.get('description'),
            markdown_content=tweet_data.get('markdown_content'),
            raw_json_content=tweet_data.get('raw_json_content'),
            kb_media_paths=tweet_data.get('kb_media_paths'),
            
            # Metadata
            source=tweet_data.get('source', 'twitter'),
            source_url=tweet_data.get('source_url'),
            
            # Error tracking
            kbitem_error=tweet_data.get('kbitem_error'),
            llm_error=tweet_data.get('llm_error'),
            retry_count=tweet_data.get('retry_count', 0)
        )
        
        return unified_tweet