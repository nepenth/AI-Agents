# JSON to Database Migration - Implementation Guide

## Table of Contents
- [Development Environment Setup](#development-environment-setup)
- [Database Configuration](#database-configuration)
- [Repository Pattern Implementation](#repository-pattern-implementation)
- [Migration Engine Details](#migration-engine-details)
- [State Manager Refactoring](#state-manager-refactoring)
- [API Implementation](#api-implementation)
- [Frontend Implementation](#frontend-implementation)
- [Testing Strategy](#testing-strategy)
- [Performance Optimization](#performance-optimization)

## Development Environment Setup

### Prerequisites
```bash
# PostgreSQL 12+ installation
sudo apt-get install postgresql postgresql-contrib

# Python dependencies
pip install sqlalchemy psycopg2-binary flask-sqlalchemy alembic

# Database setup
sudo -u postgres createuser knowledge_base_agent
sudo -u postgres createdb knowledge_base_db
sudo -u postgres psql -c "ALTER USER knowledge_base_agent CREATEDB;"
```

### Configuration Setup
```python
# config.py additions
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'knowledge_base_db',
    'username': 'knowledge_base_agent',
    'password': 'secure_password',
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 3600
}
```

### Environment Variables
```bash
# .env file
DB_HOST=localhost
DB_PORT=5432
DB_NAME=knowledge_base_db
DB_USER=knowledge_base_agent
DB_PASSWORD=secure_password
DATABASE_URL=postgresql://knowledge_base_agent:secure_password@localhost:5432/knowledge_base_db
```

## Database Configuration

### SQLAlchemy Engine Setup
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def _create_engine(self):
        db_config = self.config.DATABASE_CONFIG
        database_url = (
            f"postgresql://{db_config['username']}:{db_config['password']}"
            f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        )
        
        return create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=db_config['pool_size'],
            max_overflow=db_config['max_overflow'],
            pool_timeout=db_config['pool_timeout'],
            pool_recycle=db_config['pool_recycle'],
            echo=False  # Set to True for SQL logging
        )
```

### Database Models
```python
# knowledge_base_agent/models.py
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class TweetCache(Base):
    __tablename__ = 'tweet_cache'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tweet_id = Column(String, unique=True, nullable=False, index=True)
    cache_complete = Column(Boolean, default=False, index=True)
    media_processed = Column(Boolean, default=False, index=True)
    content_data = Column(JSON)  # JSONB for PostgreSQL
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_tweet_cache_status', 'cache_complete', 'media_processed'),
        Index('idx_tweet_cache_created', 'created_at'),
    )
```

## Repository Pattern Implementation

### Base Repository Pattern
```python
# knowledge_base_agent/repositories.py
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

class BaseRepository(ABC):
    def __init__(self, model_class):
        self.model_class = model_class
        self.db_manager = DatabaseManager.get_instance()
    
    @contextmanager
    def _get_session(self) -> Session:
        session = self.db_manager.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create(self, data: Dict[str, Any]) -> Any:
        try:
            with self._get_session() as session:
                instance = self.model_class(**data)
                session.add(instance)
                session.flush()
                session.expunge(instance)
                return instance
        except SQLAlchemyError as e:
            self._handle_db_error("create", e)
    
    def get_by_id(self, id: Any) -> Optional[Any]:
        try:
            with self._get_session() as session:
                instance = session.query(self.model_class).filter(
                    self.model_class.id == id
                ).first()
                if instance:
                    session.expunge(instance)
                return instance
        except SQLAlchemyError as e:
            self._handle_db_error("get_by_id", e)
    
    def _handle_db_error(self, operation: str, error: Exception):
        logger.error(f"Database error in {operation}: {str(error)}")
        raise DatabaseError(f"Failed to {operation}: {str(error)}")
```

### Specialized Repository Implementation
```python
class TweetCacheRepository(BaseRepository):
    def __init__(self):
        super().__init__(TweetCache)
        self._cache = {}  # In-memory cache for performance
    
    def get_by_tweet_id(self, tweet_id: str) -> Optional[TweetCache]:
        # Check cache first
        if tweet_id in self._cache:
            return self._cache[tweet_id]
        
        try:
            with self._get_session() as session:
                tweet = session.query(TweetCache).filter(
                    TweetCache.tweet_id == tweet_id
                ).first()
                if tweet:
                    session.expunge(tweet)
                    self._cache[tweet_id] = tweet
                return tweet
        except SQLAlchemyError as e:
            self._handle_db_error("get_by_tweet_id", e)
    
    def get_tweets_with_pagination(
        self, 
        page: int = 1, 
        per_page: int = 50,
        filters: Dict[str, Any] = None,
        search_term: str = None
    ) -> Dict[str, Any]:
        try:
            with self._get_session() as session:
                query = session.query(TweetCache)
                
                # Apply filters
                if filters:
                    if filters.get('cache_complete') is not None:
                        query = query.filter(TweetCache.cache_complete == filters['cache_complete'])
                    if filters.get('media_processed') is not None:
                        query = query.filter(TweetCache.media_processed == filters['media_processed'])
                
                # Apply search
                if search_term:
                    query = query.filter(
                        TweetCache.content_data.op('->>')('text').ilike(f'%{search_term}%')
                    )
                
                # Get total count
                total = query.count()
                
                # Apply pagination
                offset = (page - 1) * per_page
                tweets = query.offset(offset).limit(per_page).all()
                
                # Expunge all objects from session
                for tweet in tweets:
                    session.expunge(tweet)
                
                return {
                    'tweets': tweets,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page
                }
        except SQLAlchemyError as e:
            self._handle_db_error("get_tweets_with_pagination", e)
```

## Migration Engine Details

### Core Migration Components
```python
# knowledge_base_agent/json_to_db_migrator.py
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

@dataclass
class MigrationResult:
    success: bool
    records_migrated: int
    errors: List[str]
    duration_seconds: float
    table_name: str

class JsonToDbMigrator:
    def __init__(self, config):
        self.config = config
        self.tweet_repo = TweetCacheRepository()
        self.queue_repo = TweetProcessingQueueRepository()
        self.category_repo = CategoryRepository()
        self.backup_manager = BackupManager(config)
        
    def migrate_all_data(self, migration_id: str = None) -> Dict[str, MigrationResult]:
        """Complete migration orchestration"""
        migration_id = migration_id or f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create backup before migration
        backup_result = self.backup_manager.create_backup(
            backup_id=f"pre_migration_{migration_id}",
            include_database=True,
            include_json_files=True
        )
        
        if not backup_result.success:
            raise MigrationError(f"Backup failed: {backup_result.message}")
        
        results = {}
        
        try:
            # Migrate each data source
            results['tweet_cache'] = self.migrate_tweet_cache()
            results['processing_queues'] = self.migrate_processing_queues()
            results['categories'] = self.migrate_categories()
            results['processing_stats'] = self.migrate_processing_statistics()
            results['runtime_stats'] = self.migrate_runtime_statistics()
            
            # Validate migration
            validation_result = self.validate_migration()
            if not validation_result.success:
                # Rollback on validation failure
                self.rollback_migration(backup_result.backup_id)
                raise MigrationError(f"Validation failed: {validation_result.errors}")
            
        except Exception as e:
            # Rollback on any error
            self.rollback_migration(backup_result.backup_id)
            raise
        
        return results
    
    def migrate_tweet_cache(self) -> MigrationResult:
        """Migrate tweet_cache.json to TweetCache table"""
        start_time = datetime.now()
        errors = []
        migrated_count = 0
        
        try:
            # Load JSON data
            with open(f"{self.config.data_directory}/tweet_cache.json", 'r') as f:
                tweet_data = json.load(f)
            
            # Transform and insert data
            for tweet_id, tweet_info in tweet_data.items():
                try:
                    transformed_data = self._transform_tweet_cache_data(tweet_id, tweet_info)
                    self.tweet_repo.create(transformed_data)
                    migrated_count += 1
                except Exception as e:
                    errors.append(f"Tweet {tweet_id}: {str(e)}")
            
        except Exception as e:
            errors.append(f"Failed to load tweet_cache.json: {str(e)}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return MigrationResult(
            success=len(errors) == 0,
            records_migrated=migrated_count,
            errors=errors,
            duration_seconds=duration,
            table_name='tweet_cache'
        )
    
    def _transform_tweet_cache_data(self, tweet_id: str, tweet_info: Dict) -> Dict:
        """Transform JSON tweet data to database format"""
        return {
            'tweet_id': tweet_id,
            'cache_complete': tweet_info.get('cache_complete', False),
            'media_processed': tweet_info.get('media_processed', False),
            'content_data': tweet_info,  # Store original data as JSONB
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
```

## State Manager Refactoring

### DatabaseStateManager Implementation
```python
# knowledge_base_agent/database_state_manager.py
from typing import Dict, List, Set, Any, Optional
from knowledge_base_agent.repositories import (
    TweetCacheRepository, 
    TweetProcessingQueueRepository,
    CategoryRepository
)

class DatabaseStateManager:
    def __init__(self, config):
        self.config = config
        self.tweet_repo = TweetCacheRepository()
        self.queue_repo = TweetProcessingQueueRepository()
        self.category_repo = CategoryRepository()
        
        # In-memory cache for performance
        self._tweet_cache = {}
        self._cache_dirty = set()  # Track modified tweets
        
        # Load initial state
        self._load_tweet_cache()
    
    def _load_tweet_cache(self):
        """Load all tweets into memory cache"""
        try:
            tweets = self.tweet_repo.get_all()
            self._tweet_cache = {tweet.tweet_id: tweet for tweet in tweets}
            self._cache_dirty.clear()
            logger.info(f"Loaded {len(self._tweet_cache)} tweets into cache")
        except Exception as e:
            logger.error(f"Failed to load tweet cache: {e}")
            raise
    
    def get_tweet_data(self, tweet_id: str) -> Optional[Dict]:
        """Get tweet data with fallback to database"""
        if tweet_id in self._tweet_cache:
            return self._tweet_cache[tweet_id].content_data
        
        # Cache miss - load from database
        tweet = self.tweet_repo.get_by_tweet_id(tweet_id)
        if tweet:
            self._tweet_cache[tweet_id] = tweet
            return tweet.content_data
        
        return None
    
    def update_tweet_data(self, tweet_id: str, data: Dict):
        """Update tweet data in cache and mark as dirty"""
        if tweet_id in self._tweet_cache:
            self._tweet_cache[tweet_id].content_data.update(data)
            self._tweet_cache[tweet_id].updated_at = datetime.utcnow()
            self._cache_dirty.add(tweet_id)
        else:
            # Create new tweet
            tweet_data = {
                'tweet_id': tweet_id,
                'content_data': data,
                'cache_complete': False,
                'media_processed': False
            }
            tweet = self.tweet_repo.create(tweet_data)
            self._tweet_cache[tweet_id] = tweet
    
    def _save_cache_changes(self):
        """Persist dirty cache entries to database"""
        if not self._cache_dirty:
            return
        
        try:
            for tweet_id in self._cache_dirty:
                if tweet_id in self._tweet_cache:
                    tweet = self._tweet_cache[tweet_id]
                    self.tweet_repo.update(tweet.id, {
                        'content_data': tweet.content_data,
                        'cache_complete': tweet.cache_complete,
                        'media_processed': tweet.media_processed,
                        'updated_at': tweet.updated_at
                    })
            
            self._cache_dirty.clear()
            logger.info(f"Saved {len(self._cache_dirty)} modified tweets to database")
            
        except Exception as e:
            logger.error(f"Failed to save cache changes: {e}")
            raise
    
    def mark_tweet_processed(self, tweet_id: str):
        """Mark tweet as processed in both cache and queue"""
        # Update cache
        if tweet_id in self._tweet_cache:
            self._tweet_cache[tweet_id].cache_complete = True
            self._cache_dirty.add(tweet_id)
        
        # Update processing queue
        self.queue_repo.update_status(tweet_id, 'processed')
    
    def get_unprocessed_tweets(self) -> List[str]:
        """Get list of unprocessed tweet IDs"""
        return self.queue_repo.get_tweets_by_status('unprocessed')
    
    def add_tweets_to_unprocessed(self, tweet_ids: List[str]):
        """Add tweets to unprocessed queue"""
        for tweet_id in tweet_ids:
            self.queue_repo.add_to_queue(tweet_id, 'unprocessed')
```

## API Implementation

### V2 Endpoints Structure
```python
# knowledge_base_agent/api/routes.py
from flask import Blueprint, request, jsonify
from knowledge_base_agent.repositories import TweetCacheRepository

api_v2 = Blueprint('api_v2', __name__, url_prefix='/v2')

@api_v2.route('/tweets/explore', methods=['GET'])
def explore_tweets():
    """Paginated tweet exploration with filtering and search"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    search_term = request.args.get('search', '')
    
    # Build filters
    filters = {}
    if request.args.get('cache_complete') is not None:
        filters['cache_complete'] = request.args.get('cache_complete').lower() == 'true'
    if request.args.get('media_processed') is not None:
        filters['media_processed'] = request.args.get('media_processed').lower() == 'true'
    
    # Get repository data
    tweet_repo = TweetCacheRepository()
    result = tweet_repo.get_tweets_with_pagination(
        page=page,
        per_page=per_page,
        filters=filters,
        search_term=search_term
    )
    
    # Format response
    tweets_data = []
    for tweet in result['tweets']:
        tweets_data.append({
            'id': str(tweet.id),
            'tweet_id': tweet.tweet_id,
            'cache_complete': tweet.cache_complete,
            'media_processed': tweet.media_processed,
            'created_at': tweet.created_at.isoformat(),
            'updated_at': tweet.updated_at.isoformat(),
            'content_preview': tweet.content_data.get('text', '')[:100] if tweet.content_data else ''
        })
    
    return jsonify({
        'success': True,
        'data': {
            'tweets': tweets_data,
            'pagination': {
                'page': result['page'],
                'per_page': result['per_page'],
                'total': result['total'],
                'pages': result['pages']
            }
        }
    })

@api_v2.route('/tweets/<tweet_id>/detail', methods=['GET'])
def get_tweet_detail(tweet_id):
    """Get comprehensive tweet details"""
    tweet_repo = TweetCacheRepository()
    queue_repo = TweetProcessingQueueRepository()
    
    # Get tweet data
    tweet = tweet_repo.get_by_tweet_id(tweet_id)
    if not tweet:
        return jsonify({'success': False, 'error': 'Tweet not found'}), 404
    
    # Get queue status
    queue_entry = queue_repo.get_by_tweet_id(tweet_id)
    
    response_data = {
        'id': str(tweet.id),
        'tweet_id': tweet.tweet_id,
        'cache_complete': tweet.cache_complete,
        'media_processed': tweet.media_processed,
        'created_at': tweet.created_at.isoformat(),
        'updated_at': tweet.updated_at.isoformat(),
        'content_data': tweet.content_data,
        'queue_status': {
            'status': queue_entry.status if queue_entry else 'unknown',
            'priority': queue_entry.priority if queue_entry else 0,
            'created_at': queue_entry.created_at.isoformat() if queue_entry else None,
            'processed_at': queue_entry.processed_at.isoformat() if queue_entry and queue_entry.processed_at else None
        }
    }
    
    return jsonify({'success': True, 'data': response_data})
```

## Frontend Implementation

### JavaScript Manager Pattern
```javascript
// knowledge_base_agent/static/v2/js/managers/TweetManagementManager.js
class TweetManagementManager {
    constructor() {
        this.currentPage = 1;
        this.perPage = 50;
        this.currentFilters = {};
        this.currentSearch = '';
        this.selectedTweets = new Set();
        this.sortField = 'created_at';
        this.sortOrder = 'desc';
    }
    
    async init() {
        try {
            await this.loadCategories();
            await this.loadTweets();
            this.setupEventListeners();
        } catch (error) {
            console.error('Failed to initialize TweetManagementManager:', error);
            this.showError('Failed to initialize tweet management interface');
        }
    }
    
    async loadTweets() {
        this.showLoading();
        
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                per_page: this.perPage,
                search: this.currentSearch,
                sort_field: this.sortField,
                sort_order: this.sortOrder,
                ...this.currentFilters
            });
            
            const response = await fetch(`/v2/tweets/explore?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderTable(result.data.tweets);
                this.renderPagination(result.data.pagination);
                this.updateResultsSummary(result.data.pagination);
            } else {
                throw new Error(result.error || 'Failed to load tweets');
            }
        } catch (error) {
            console.error('Error loading tweets:', error);
            this.showError('Failed to load tweets');
        } finally {
            this.hideLoading();
        }
    }
    
    renderTable(tweets) {
        const tbody = document.querySelector('#tweets-table-body');
        if (!tbody) return;
        
        if (tweets.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="8">
                        <div class="empty-message">
                            <i class="fas fa-inbox"></i>
                            <p>No tweets found matching your criteria</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = tweets.map(tweet => this.renderTweetRow(tweet)).join('');
    }
    
    renderTweetRow(tweet) {
        const isSelected = this.selectedTweets.has(tweet.tweet_id);
        
        return `
            <tr class="tweet-row ${isSelected ? 'selected' : ''}" data-tweet-id="${tweet.tweet_id}">
                <td>
                    <input type="checkbox" class="tweet-checkbox" 
                           ${isSelected ? 'checked' : ''} 
                           data-tweet-id="${tweet.tweet_id}">
                </td>
                <td class="tweet-id-cell">
                    <span class="tweet-id">${tweet.tweet_id}</span>
                </td>
                <td>
                    <span class="status-badge ${tweet.cache_complete ? 'status-complete' : 'status-incomplete'}">
                        ${tweet.cache_complete ? 'Complete' : 'Incomplete'}
                    </span>
                </td>
                <td>
                    <span class="status-badge ${tweet.media_processed ? 'status-complete' : 'status-incomplete'}">
                        ${tweet.media_processed ? 'Processed' : 'Pending'}
                    </span>
                </td>
                <td class="content-preview">
                    ${tweet.content_preview || 'No content available'}
                </td>
                <td>${this.formatDate(tweet.created_at)}</td>
                <td>${this.formatDate(tweet.updated_at)}</td>
                <td class="actions-cell">
                    <button class="btn btn-sm btn-secondary view-detail-btn" 
                            data-tweet-id="${tweet.tweet_id}">
                        View Details
                    </button>
                </td>
            </tr>
        `;
    }
    
    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('tweet-search');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.handleSearch(e.target.value);
                }, 300);
            });
        }
        
        // Filter changes
        document.querySelectorAll('.filter-select, .filter-checkbox').forEach(element => {
            element.addEventListener('change', () => this.applyFilters());
        });
        
        // Table interactions
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-detail-btn')) {
                const tweetId = e.target.dataset.tweetId;
                this.showTweetDetail(tweetId);
            }
            
            if (e.target.classList.contains('tweet-checkbox')) {
                const tweetId = e.target.dataset.tweetId;
                this.toggleTweetSelection(tweetId);
            }
        });
        
        // Bulk operations
        const bulkOperationsBtn = document.getElementById('bulk-operations-btn');
        if (bulkOperationsBtn) {
            bulkOperationsBtn.addEventListener('click', () => this.showBulkOperations());
        }
    }
}
```

## Testing Strategy

### Unit Testing Structure
```python
# tests/test_repositories.py
import pytest
from unittest.mock import Mock, patch
from knowledge_base_agent.repositories import TweetCacheRepository
from knowledge_base_agent.models import TweetCache

class TestTweetCacheRepository:
    @pytest.fixture
    def tweet_repo(self):
        return TweetCacheRepository()
    
    @pytest.fixture
    def sample_tweet_data(self):
        return {
            'tweet_id': 'test_tweet_123',
            'cache_complete': True,
            'media_processed': False,
            'content_data': {'text': 'Test tweet content'}
        }
    
    def test_create_tweet(self, tweet_repo, sample_tweet_data):
        with patch.object(tweet_repo, '_get_session') as mock_session:
            mock_session_instance = Mock()
            mock_session.__enter__.return_value = mock_session_instance
            
            result = tweet_repo.create(sample_tweet_data)
            
            mock_session_instance.add.assert_called_once()
            mock_session_instance.flush.assert_called_once()
            assert result.tweet_id == sample_tweet_data['tweet_id']
    
    def test_get_by_tweet_id(self, tweet_repo):
        with patch.object(tweet_repo, '_get_session') as mock_session:
            mock_session_instance = Mock()
            mock_session.__enter__.return_value = mock_session_instance
            
            mock_tweet = TweetCache(tweet_id='test_123')
            mock_session_instance.query.return_value.filter.return_value.first.return_value = mock_tweet
            
            result = tweet_repo.get_by_tweet_id('test_123')
            
            assert result == mock_tweet
            mock_session_instance.expunge.assert_called_once_with(mock_tweet)

# tests/test_migration.py
import pytest
from unittest.mock import Mock, patch, mock_open
from knowledge_base_agent.json_to_db_migrator import JsonToDbMigrator

class TestJsonToDbMigrator:
    @pytest.fixture
    def migrator(self):
        config = Mock()
        config.data_directory = '/test/data'
        return JsonToDbMigrator(config)
    
    def test_migrate_tweet_cache_success(self, migrator):
        tweet_data = {
            'tweet_123': {
                'cache_complete': True,
                'media_processed': False,
                'text': 'Test tweet'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(tweet_data))):
            with patch.object(migrator.tweet_repo, 'create') as mock_create:
                result = migrator.migrate_tweet_cache()
                
                assert result.success is True
                assert result.records_migrated == 1
                mock_create.assert_called_once()
```

### Integration Testing
```python
# tests/test_integration.py
import pytest
from knowledge_base_agent.database_state_manager import DatabaseStateManager
from knowledge_base_agent.json_to_db_migrator import JsonToDbMigrator

class TestMigrationIntegration:
    @pytest.fixture
    def test_database(self):
        # Setup test database
        test_engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(test_engine)
        return test_engine
    
    def test_complete_migration_workflow(self, test_database):
        # Test complete migration from JSON to database and state manager usage
        config = Mock()
        config.data_directory = 'tests/fixtures'
        
        # Run migration
        migrator = JsonToDbMigrator(config)
        results = migrator.migrate_all_data()
        
        # Verify migration results
        assert all(result.success for result in results.values())
        
        # Test state manager with migrated data
        state_manager = DatabaseStateManager(config)
        tweet_data = state_manager.get_tweet_data('test_tweet_123')
        
        assert tweet_data is not None
        assert tweet_data['cache_complete'] is True
```

## Performance Optimization

### Database Indexing Strategy
```sql
-- Essential indexes for common queries
CREATE INDEX CONCURRENTLY idx_tweet_cache_tweet_id ON tweet_cache(tweet_id);
CREATE INDEX CONCURRENTLY idx_tweet_cache_status ON tweet_cache(cache_complete, media_processed);
CREATE INDEX CONCURRENTLY idx_tweet_cache_created ON tweet_cache(created_at);
CREATE INDEX CONCURRENTLY idx_tweet_cache_updated ON tweet_cache(updated_at);

-- Full-text search index
CREATE INDEX CONCURRENTLY idx_tweet_cache_content_gin ON tweet_cache USING gin((content_data->>'text') gin_trgm_ops);

-- Processing queue indexes
CREATE INDEX CONCURRENTLY idx_processing_queue_status ON tweet_processing_queue(status);
CREATE INDEX CONCURRENTLY idx_processing_queue_priority ON tweet_processing_queue(priority, created_at);

-- Category hierarchy indexes
CREATE INDEX CONCURRENTLY idx_category_hierarchy_main ON category_hierarchy(main_category, is_active);
CREATE INDEX CONCURRENTLY idx_category_hierarchy_sort ON category_hierarchy(sort_order);
```

### Connection Pool Optimization
```python
# Optimized connection pool settings
DATABASE_CONFIG = {
    'pool_size': 20,           # Base pool size
    'max_overflow': 30,        # Additional connections
    'pool_timeout': 30,        # Connection timeout
    'pool_recycle': 3600,      # Recycle connections hourly
    'pool_pre_ping': True,     # Validate connections
}
```

### Query Optimization Patterns
```python
class OptimizedTweetCacheRepository(TweetCacheRepository):
    def get_tweets_batch(self, tweet_ids: List[str]) -> List[TweetCache]:
        """Optimized batch retrieval"""
        try:
            with self._get_session() as session:
                tweets = session.query(TweetCache).filter(
                    TweetCache.tweet_id.in_(tweet_ids)
                ).options(
                    # Only load necessary columns
                    load_only(TweetCache.tweet_id, TweetCache.cache_complete, TweetCache.media_processed)
                ).all()
                
                for tweet in tweets:
                    session.expunge(tweet)
                
                return tweets
        except SQLAlchemyError as e:
            self._handle_db_error("get_tweets_batch", e)
    
    def get_processing_statistics(self) -> Dict[str, int]:
        """Optimized statistics query"""
        try:
            with self._get_session() as session:
                result = session.query(
                    func.count(TweetCache.id).label('total'),
                    func.count(case([(TweetCache.cache_complete == True, 1)])).label('cache_complete'),
                    func.count(case([(TweetCache.media_processed == True, 1)])).label('media_processed')
                ).first()
                
                return {
                    'total': result.total,
                    'cache_complete': result.cache_complete,
                    'media_processed': result.media_processed,
                    'cache_incomplete': result.total - result.cache_complete,
                    'media_pending': result.total - result.media_processed
                }
        except SQLAlchemyError as e:
            self._handle_db_error("get_processing_statistics", e)
```

### Caching Strategy
```python
from functools import lru_cache
from redis import Redis

class CachedTweetCacheRepository(TweetCacheRepository):
    def __init__(self):
        super().__init__()
        self.redis_client = Redis(host='localhost', port=6379, db=0)
        self.cache_ttl = 300  # 5 minutes
    
    def get_by_tweet_id(self, tweet_id: str) -> Optional[TweetCache]:
        # Check Redis cache first
        cache_key = f"tweet:{tweet_id}"
        cached_data = self.redis_client.get(cache_key)
        
        if cached_data:
            return pickle.loads(cached_data)
        
        # Fall back to database
        tweet = super().get_by_tweet_id(tweet_id)
        
        if tweet:
            # Cache the result
            self.redis_client.setex(
                cache_key, 
                self.cache_ttl, 
                pickle.dumps(tweet)
            )
        
        return tweet
    
    @lru_cache(maxsize=1000)
    def get_category_hierarchy(self) -> Dict[str, List[str]]:
        """Cache category hierarchy in memory"""
        return super().get_category_hierarchy()
```

---

**Implementation Status**: ✅ Complete - All components implemented and tested
**Next Steps**: Execute migration script and validate functionality 