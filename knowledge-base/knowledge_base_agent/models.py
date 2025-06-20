from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

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
    synthesis_short_name = db.Column(db.String(50), nullable=True)
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
        if self.sub_category:
            return f'<SubcategorySynthesis {self.main_category}/{self.sub_category}>'
        return f'<MainCategorySynthesis {self.main_category}>'

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