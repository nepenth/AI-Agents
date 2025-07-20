from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
    kb_media_paths = db.Column(db.Text, nullable=True)
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
    Track Celery task execution state, extending current state management.
    This provides a persistent record of each task run, unlike the ephemeral
    nature of the AgentState singleton.
    """
    __tablename__ = 'celery_task_state'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), unique=True, nullable=False, index=True)  # Custom-generated UUID
    celery_task_id = db.Column(db.String(36), nullable=True, index=True) # Celery's internal task ID
    task_type = db.Column(db.String(100), nullable=False, index=True)  # e.g., 'knowledge_base_agent.tasks.run_agent'
    status = db.Column(db.String(20), nullable=False, default='PENDING', index=True)  # PENDING, PROGRESS, SUCCESS, FAILURE, REVOKED
    
    # Progress tracking fields
    current_phase_id = db.Column(db.String(50), nullable=True)
    current_phase_message = db.Column(db.Text, nullable=True)
    progress_percentage = db.Column(db.Integer, default=0)
    
    # Task metadata
    human_readable_name = db.Column(db.String(200), nullable=True)  # Human-readable task name with timestamp
    preferences = db.Column(db.JSON, nullable=True)  # Store UserPreferences as JSON for agent runs
    result_data = db.Column(db.JSON, nullable=True)  # Store task final results
    run_report = db.Column(db.JSON, nullable=True)  # Store detailed run report
    error_message = db.Column(db.Text, nullable=True)
    traceback = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, task_id, task_type, status, preferences=None, celery_task_id=None, current_phase_id=None, current_phase_message=None, progress_percentage=0, result_data=None, error_message=None, traceback=None, human_readable_name=None, run_report=None):
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