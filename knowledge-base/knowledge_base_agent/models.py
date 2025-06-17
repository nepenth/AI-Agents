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