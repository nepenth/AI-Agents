"""
SQLAlchemy Model Analyzer

Analyzes database models to extract field information, relationships,
constraints, and generate comprehensive documentation.
"""

import inspect
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import TypeEngine
import json

logger = logging.getLogger(__name__)


@dataclass
class FieldInfo:
    """Information about a database field."""
    name: str
    type: str
    nullable: bool
    primary_key: bool
    unique: bool
    default: Optional[Any]
    foreign_key: Optional[str]
    description: Optional[str]
    max_length: Optional[int] = None
    index: bool = False


@dataclass
class RelationshipInfo:
    """Information about model relationships."""
    name: str
    target_model: str
    relationship_type: str  # 'one-to-one', 'one-to-many', 'many-to-one', 'many-to-many'
    foreign_key: Optional[str]
    back_populates: Optional[str]
    cascade: Optional[str]
    lazy: Optional[str]


@dataclass
class ConstraintInfo:
    """Information about database constraints."""
    name: str
    type: str  # 'unique', 'check', 'foreign_key', 'primary_key'
    columns: List[str]
    description: Optional[str] = None


@dataclass
class IndexInfo:
    """Information about database indexes."""
    name: str
    columns: List[str]
    unique: bool
    description: Optional[str] = None


@dataclass
class ModelDocumentation:
    """Comprehensive documentation for a database model."""
    name: str
    table_name: str
    description: str
    purpose: str
    
    # Structure
    fields: List[FieldInfo]
    relationships: List[RelationshipInfo]
    constraints: List[ConstraintInfo]
    indexes: List[IndexInfo]
    
    # Metadata
    primary_keys: List[str]
    foreign_keys: List[str]
    unique_fields: List[str]
    required_fields: List[str]
    optional_fields: List[str]
    
    # Usage patterns
    common_queries: List[str]
    related_models: List[str]
    business_rules: List[str]


class SQLAlchemyModelAnalyzer:
    """Analyzes SQLAlchemy models and generates comprehensive documentation."""
    
    def __init__(self, db: SQLAlchemy):
        self.db = db
        self.models: Dict[str, Any] = {}
        self.model_docs: List[ModelDocumentation] = []
        
    def analyze_models(self) -> Dict[str, Any]:
        """Analyze all SQLAlchemy models and generate documentation."""
        logger.info("Starting SQLAlchemy model analysis...")
        
        # Discover all models
        self._discover_models()
        
        # Analyze each model
        for model_name, model_class in self.models.items():
            try:
                doc = self._analyze_model(model_name, model_class)
                self.model_docs.append(doc)
            except Exception as e:
                logger.error(f"Error analyzing model {model_name}: {e}")
        
        # Generate comprehensive documentation
        documentation = self._generate_documentation()
        
        logger.info(f"Model analysis completed. Analyzed {len(self.model_docs)} models")
        return documentation
    
    def _discover_models(self):
        """Discover all SQLAlchemy models."""
        # Get all models from the registry
        for mapper in self.db.Model.registry.mappers:
            model_class = mapper.class_
            model_name = model_class.__name__
            self.models[model_name] = model_class
    
    def _analyze_model(self, model_name: str, model_class) -> ModelDocumentation:
        """Analyze a single SQLAlchemy model."""
        # Extract basic information
        table_name = model_class.__tablename__
        description = self._extract_model_description(model_class)
        purpose = self._extract_model_purpose(model_name, model_class)
        
        # Analyze fields
        fields = self._analyze_fields(model_class)
        
        # Analyze relationships
        relationships = self._analyze_relationships(model_class)
        
        # Analyze constraints
        constraints = self._analyze_constraints(model_class)
        
        # Analyze indexes
        indexes = self._analyze_indexes(model_class)
        
        # Extract metadata
        primary_keys = [f.name for f in fields if f.primary_key]
        foreign_keys = [f.name for f in fields if f.foreign_key]
        unique_fields = [f.name for f in fields if f.unique]
        required_fields = [f.name for f in fields if not f.nullable and not f.primary_key]
        optional_fields = [f.name for f in fields if f.nullable]
        
        # Generate usage patterns
        common_queries = self._generate_common_queries(model_name, fields, relationships)
        related_models = [r.target_model for r in relationships]
        business_rules = self._extract_business_rules(model_name, model_class)
        
        return ModelDocumentation(
            name=model_name,
            table_name=table_name,
            description=description,
            purpose=purpose,
            fields=fields,
            relationships=relationships,
            constraints=constraints,
            indexes=indexes,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            unique_fields=unique_fields,
            required_fields=required_fields,
            optional_fields=optional_fields,
            common_queries=common_queries,
            related_models=related_models,
            business_rules=business_rules
        )
    
    def _extract_model_description(self, model_class) -> str:
        """Extract description from model docstring."""
        docstring = inspect.getdoc(model_class)
        if docstring:
            # Take first line as description
            return docstring.split('\n')[0].strip()
        return f"Database model for {model_class.__name__}"
    
    def _extract_model_purpose(self, model_name: str, model_class) -> str:
        """Extract or infer the purpose of the model."""
        purposes = {
            'KnowledgeBaseItem': 'Stores processed knowledge base items with content, categorization, and metadata',
            'SubcategorySynthesis': 'Stores AI-generated synthesis documents that summarize knowledge base items by category',
            'AgentState': 'Singleton table tracking the operational state of the Knowledge Base Agent',
            'CeleryTaskState': 'Tracks execution state and progress of Celery background tasks',
            'ChatSession': 'Manages conversational AI chat sessions with metadata and message tracking',
            'ChatMessage': 'Stores individual messages within chat sessions with AI response metadata',
            'Embedding': 'Stores vector embeddings for knowledge base items and synthesis documents',
            'Schedule': 'Manages automated scheduling for recurring agent execution tasks',
            'ScheduleRun': 'Records execution history and results of scheduled agent runs',
            'Setting': 'Stores system configuration key-value pairs'
        }
        
        return purposes.get(model_name, f"Database model for {model_name} entities")
    
    def _analyze_fields(self, model_class) -> List[FieldInfo]:
        """Analyze all fields in a model."""
        fields = []
        
        # Get all columns from the model
        for column_name, column in model_class.__table__.columns.items():
            field_info = self._analyze_field(column_name, column)
            fields.append(field_info)
        
        return fields
    
    def _analyze_field(self, column_name: str, column: Column) -> FieldInfo:
        """Analyze a single field/column."""
        # Extract type information
        field_type = self._get_field_type(column.type)
        
        # Extract constraints and properties
        nullable = column.nullable
        primary_key = column.primary_key
        unique = column.unique
        default = self._get_default_value(column.default)
        foreign_key = self._get_foreign_key(column)
        max_length = self._get_max_length(column.type)
        index = column.index if hasattr(column, 'index') else False
        
        # Generate description
        description = self._generate_field_description(column_name, field_type)
        
        return FieldInfo(
            name=column_name,
            type=field_type,
            nullable=nullable,
            primary_key=primary_key,
            unique=unique,
            default=default,
            foreign_key=foreign_key,
            description=description,
            max_length=max_length,
            index=index
        )
    
    def _get_field_type(self, sql_type: TypeEngine) -> str:
        """Convert SQLAlchemy type to string representation."""
        type_mapping = {
            'INTEGER': 'integer',
            'VARCHAR': 'string',
            'TEXT': 'text',
            'DATETIME': 'datetime',
            'BOOLEAN': 'boolean',
            'JSON': 'json',
            'BLOB': 'binary'
        }
        
        type_str = str(sql_type).upper()
        for sql_type_name, mapped_type in type_mapping.items():
            if sql_type_name in type_str:
                return mapped_type
        
        return str(sql_type).lower()
    
    def _get_default_value(self, default) -> Optional[Any]:
        """Extract default value from column."""
        if default is None:
            return None
        
        if hasattr(default, 'arg'):
            if callable(default.arg):
                return f"function: {default.arg.__name__}"
            return default.arg
        
        return str(default)
    
    def _get_foreign_key(self, column: Column) -> Optional[str]:
        """Extract foreign key reference."""
        if column.foreign_keys:
            fk = list(column.foreign_keys)[0]
            return f"{fk.column.table.name}.{fk.column.name}"
        return None
    
    def _get_max_length(self, sql_type: TypeEngine) -> Optional[int]:
        """Extract maximum length for string types."""
        if hasattr(sql_type, 'length') and sql_type.length:
            return sql_type.length
        return None
    
    def _generate_field_description(self, field_name: str, field_type: str) -> str:
        """Generate description for a field based on its name and type."""
        descriptions = {
            'id': 'Primary key identifier',
            'created_at': 'Timestamp when record was created',
            'updated_at': 'Timestamp when record was last updated',
            'last_updated': 'Timestamp when record was last updated',
            'title': 'Title or name of the item',
            'content': 'Main content or body text',
            'description': 'Description or summary text',
            'status': 'Current status of the item',
            'enabled': 'Whether the item is enabled/active',
            'is_archived': 'Whether the item is archived',
            'task_id': 'Unique identifier for task tracking',
            'session_id': 'Unique identifier for session tracking',
            'user_id': 'Reference to user who owns this record',
            'name': 'Name or identifier',
            'email': 'Email address',
            'url': 'URL or web address',
            'path': 'File system path',
            'count': 'Numeric count or quantity'
        }
        
        # Check for exact matches
        if field_name in descriptions:
            return descriptions[field_name]
        
        # Check for partial matches
        for key, desc in descriptions.items():
            if key in field_name.lower():
                return desc
        
        # Generate based on type
        if field_type == 'datetime':
            return f"Timestamp for {field_name.replace('_', ' ')}"
        elif field_type == 'boolean':
            return f"Boolean flag for {field_name.replace('_', ' ')}"
        elif field_type == 'integer':
            return f"Numeric value for {field_name.replace('_', ' ')}"
        elif field_type == 'string':
            return f"Text value for {field_name.replace('_', ' ')}"
        
        return f"Field for {field_name.replace('_', ' ')}"
    
    def _analyze_relationships(self, model_class) -> List[RelationshipInfo]:
        """Analyze relationships in a model."""
        relationships = []
        
        # Get all relationships from the model
        if hasattr(model_class, '__mapper__'):
            for rel_name, rel_property in model_class.__mapper__.relationships.items():
                rel_info = self._analyze_relationship(rel_name, rel_property)
                relationships.append(rel_info)
        
        return relationships
    
    def _analyze_relationship(self, rel_name: str, rel_property) -> RelationshipInfo:
        """Analyze a single relationship."""
        target_model = rel_property.mapper.class_.__name__
        
        # Determine relationship type
        relationship_type = self._determine_relationship_type(rel_property)
        
        # Extract foreign key
        foreign_key = None
        if rel_property.local_columns:
            local_col = list(rel_property.local_columns)[0]
            if local_col.foreign_keys:
                fk = list(local_col.foreign_keys)[0]
                foreign_key = f"{fk.column.table.name}.{fk.column.name}"
        
        # Extract other properties
        back_populates = getattr(rel_property, 'back_populates', None)
        cascade = str(rel_property.cascade) if rel_property.cascade else None
        lazy = str(rel_property.lazy) if hasattr(rel_property, 'lazy') else None
        
        return RelationshipInfo(
            name=rel_name,
            target_model=target_model,
            relationship_type=relationship_type,
            foreign_key=foreign_key,
            back_populates=back_populates,
            cascade=cascade,
            lazy=lazy
        )
    
    def _determine_relationship_type(self, rel_property) -> str:
        """Determine the type of relationship."""
        if rel_property.uselist:
            return 'one-to-many'
        else:
            # Check if it's many-to-one by looking at foreign keys
            if rel_property.local_columns:
                return 'many-to-one'
            else:
                return 'one-to-one'
    
    def _analyze_constraints(self, model_class) -> List[ConstraintInfo]:
        """Analyze constraints in a model."""
        constraints = []
        
        if hasattr(model_class, '__table__'):
            table = model_class.__table__
            
            # Analyze table constraints
            for constraint in table.constraints:
                constraint_info = self._analyze_constraint(constraint)
                if constraint_info:
                    constraints.append(constraint_info)
        
        return constraints
    
    def _analyze_constraint(self, constraint) -> Optional[ConstraintInfo]:
        """Analyze a single constraint."""
        constraint_type = type(constraint).__name__.lower().replace('constraint', '')
        
        if hasattr(constraint, 'columns'):
            columns = [col.name for col in constraint.columns]
        else:
            columns = []
        
        name = getattr(constraint, 'name', None) or f"{constraint_type}_constraint"
        
        description = self._generate_constraint_description(constraint_type, columns)
        
        return ConstraintInfo(
            name=name,
            type=constraint_type,
            columns=columns,
            description=description
        )
    
    def _generate_constraint_description(self, constraint_type: str, columns: List[str]) -> str:
        """Generate description for a constraint."""
        if constraint_type == 'unique':
            if len(columns) == 1:
                return f"Ensures {columns[0]} values are unique"
            else:
                return f"Ensures combination of {', '.join(columns)} is unique"
        elif constraint_type == 'primarykey':
            return f"Primary key constraint on {', '.join(columns)}"
        elif constraint_type == 'foreignkey':
            return f"Foreign key constraint on {', '.join(columns)}"
        else:
            return f"{constraint_type.title()} constraint on {', '.join(columns)}"
    
    def _analyze_indexes(self, model_class) -> List[IndexInfo]:
        """Analyze indexes in a model."""
        indexes = []
        
        if hasattr(model_class, '__table__'):
            table = model_class.__table__
            
            # Analyze table indexes
            for index in table.indexes:
                index_info = self._analyze_index(index)
                indexes.append(index_info)
        
        return indexes
    
    def _analyze_index(self, index) -> IndexInfo:
        """Analyze a single index."""
        name = index.name
        columns = [col.name for col in index.columns]
        unique = index.unique
        description = f"Index on {', '.join(columns)}" + (" (unique)" if unique else "")
        
        return IndexInfo(
            name=name,
            columns=columns,
            unique=unique,
            description=description
        )
    
    def _generate_common_queries(self, model_name: str, fields: List[FieldInfo], relationships: List[RelationshipInfo]) -> List[str]:
        """Generate common query patterns for a model."""
        queries = []
        
        # Basic queries
        queries.append(f"{model_name}.query.all()  # Get all records")
        
        # Primary key lookup
        pk_fields = [f for f in fields if f.primary_key]
        if pk_fields:
            pk_field = pk_fields[0].name
            queries.append(f"{model_name}.query.get(id)  # Get by {pk_field}")
        
        # Filter by common fields
        for field in fields:
            if field.name in ['status', 'enabled', 'is_archived', 'active']:
                queries.append(f"{model_name}.query.filter_by({field.name}=True).all()")
            elif field.type == 'string' and 'name' in field.name:
                queries.append(f"{model_name}.query.filter_by({field.name}='value').first()")
        
        # Relationship queries
        for rel in relationships:
            if rel.relationship_type == 'one-to-many':
                queries.append(f"instance.{rel.name}  # Access related {rel.target_model} records")
        
        # Date-based queries
        date_fields = [f for f in fields if f.type == 'datetime']
        if date_fields:
            date_field = date_fields[0].name
            queries.append(f"{model_name}.query.filter({model_name}.{date_field} >= datetime.now()).all()")
        
        return queries
    
    def _extract_business_rules(self, model_name: str, model_class) -> List[str]:
        """Extract business rules and constraints."""
        rules = []
        
        # Model-specific business rules
        business_rules = {
            'KnowledgeBaseItem': [
                'Each item must have a title and content',
                'Items are categorized into main_category and sub_category',
                'tweet_id must be unique when provided',
                'created_at and last_updated are automatically managed'
            ],
            'SubcategorySynthesis': [
                'Combination of main_category and sub_category must be unique',
                'Synthesis content is AI-generated based on related KB items',
                'item_count tracks number of source items used',
                'Dependency tracking enables incremental updates'
            ],
            'AgentState': [
                'Singleton table - only one record should exist',
                'Tracks current agent execution state and progress',
                'Links to active Celery task via current_task_id',
                'JSON fields store complex state information'
            ],
            'CeleryTaskState': [
                'Each task has unique task_id for tracking',
                'Status follows Celery state machine (PENDING → PROGRESS → SUCCESS/FAILURE)',
                'Progress tracking enables real-time UI updates',
                'Preferences and results stored as JSON'
            ],
            'ChatSession': [
                'Each session has unique session_id',
                'message_count is automatically maintained',
                'Sessions can be archived but not deleted',
                'Cascade delete removes all related messages'
            ],
            'ChatMessage': [
                'Messages belong to a chat session',
                'Role must be either "user" or "assistant"',
                'AI responses include source attribution and metrics',
                'Performance data stored for optimization'
            ],
            'Schedule': [
                'Supports multiple frequency types (manual, daily, weekly, monthly, custom)',
                'Custom schedules use cron expressions',
                'Pipeline configuration stored as JSON',
                'next_run calculated based on frequency and last execution'
            ]
        }
        
        return business_rules.get(model_name, [])
    
    def _generate_documentation(self) -> Dict[str, Any]:
        """Generate comprehensive model documentation."""
        # Group models by category
        categories = {
            'Core Data Models': ['KnowledgeBaseItem', 'SubcategorySynthesis', 'Embedding'],
            'Agent Management': ['AgentState', 'CeleryTaskState'],
            'Chat System': ['ChatSession', 'ChatMessage'],
            'Scheduling': ['Schedule', 'ScheduleRun'],
            'Configuration': ['Setting']
        }
        
        # Organize documentation by category
        by_category = {}
        for category, model_names in categories.items():
            by_category[category] = []
            for doc in self.model_docs:
                if doc.name in model_names:
                    by_category[category].append(asdict(doc))
        
        # Add uncategorized models
        categorized_models = set()
        for model_names in categories.values():
            categorized_models.update(model_names)
        
        uncategorized = []
        for doc in self.model_docs:
            if doc.name not in categorized_models:
                uncategorized.append(asdict(doc))
        
        if uncategorized:
            by_category['Other'] = uncategorized
        
        # Generate statistics
        total_models = len(self.model_docs)
        total_fields = sum(len(doc.fields) for doc in self.model_docs)
        total_relationships = sum(len(doc.relationships) for doc in self.model_docs)
        total_constraints = sum(len(doc.constraints) for doc in self.model_docs)
        
        # Generate relationship map
        relationship_map = {}
        for doc in self.model_docs:
            relationship_map[doc.name] = [rel.target_model for rel in doc.relationships]
        
        return {
            'metadata': {
                'generated_at': '2024-01-01T00:00:00Z',  # Would use actual timestamp
                'total_models': total_models,
                'total_fields': total_fields,
                'total_relationships': total_relationships,
                'total_constraints': total_constraints
            },
            'statistics': {
                'models_by_category': {cat: len(models) for cat, models in by_category.items()},
                'field_types': self._count_field_types(),
                'relationship_types': self._count_relationship_types(),
                'constraint_types': self._count_constraint_types()
            },
            'categories': by_category,
            'relationship_map': relationship_map,
            'models': [asdict(doc) for doc in self.model_docs]
        }
    
    def _count_field_types(self) -> Dict[str, int]:
        """Count field types across all models."""
        type_counts = {}
        for doc in self.model_docs:
            for field in doc.fields:
                type_counts[field.type] = type_counts.get(field.type, 0) + 1
        return type_counts
    
    def _count_relationship_types(self) -> Dict[str, int]:
        """Count relationship types across all models."""
        type_counts = {}
        for doc in self.model_docs:
            for rel in doc.relationships:
                type_counts[rel.relationship_type] = type_counts.get(rel.relationship_type, 0) + 1
        return type_counts
    
    def _count_constraint_types(self) -> Dict[str, int]:
        """Count constraint types across all models."""
        type_counts = {}
        for doc in self.model_docs:
            for constraint in doc.constraints:
                type_counts[constraint.type] = type_counts.get(constraint.type, 0) + 1
        return type_counts


def analyze_database_models(db: SQLAlchemy) -> Dict[str, Any]:
    """Analyze all database models and return comprehensive documentation."""
    analyzer = SQLAlchemyModelAnalyzer(db)
    return analyzer.analyze_models()