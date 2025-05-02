from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class KnowledgeBaseItem(db.Model):
    __tablename__ = 'knowledge_base_item'
    
    id = db.Column(db.Integer, primary_key=True)
    tweet_id = db.Column(db.String(50), unique=True, nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=False)
    main_category = db.Column(db.String(100), nullable=False, default='Uncategorized')
    sub_category = db.Column(db.String(100), nullable=False, default='Uncategorized')
    item_name = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    last_updated = db.Column(db.DateTime, nullable=False)
    file_path = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f'<KnowledgeBaseItem {self.title}>' 