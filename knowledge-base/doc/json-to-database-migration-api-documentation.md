# JSON to Database Migration - API Documentation

## Table of Contents
- [API Overview](#api-overview)
- [Authentication](#authentication)
- [Tweet Management API (V2)](#tweet-management-api-v2)
- [Backup and Recovery API](#backup-and-recovery-api)
- [Migration API](#migration-api)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [API Examples](#api-examples)

## API Overview

The JSON to Database Migration project introduces comprehensive API endpoints for managing the Knowledge Base Agent's database-backed functionality. The API follows RESTful principles and provides versioned endpoints for backward compatibility.

### Base URLs
- **V2 Endpoints**: `/v2/`
- **Backup API**: `/backup/`
- **Migration API**: `/migration/`

### Content Types
- **Request**: `application/json`
- **Response**: `application/json`

### API Versioning
- **V1**: Legacy JSON file-based endpoints (maintained for compatibility)
- **V2**: Database-backed endpoints with enhanced functionality

## Authentication

Currently, the API uses session-based authentication through the Flask application. Future versions may implement:
- API key authentication
- JWT token-based authentication
- Role-based access control

## Tweet Management API (V2)

### GET /v2/tweets/explore
**Purpose**: Paginated tweet exploration with filtering, searching, and sorting.

**Parameters**:
```json
{
  "page": 1,                    // Page number (default: 1)
  "per_page": 50,               // Results per page (max: 200, default: 50)
  "search": "keyword",          // Full-text search term
  "cache_complete": true,       // Filter by cache completion status
  "media_processed": false,     // Filter by media processing status
  "category": "technology",     // Filter by category
  "sort_field": "created_at",   // Sort field (created_at, updated_at, tweet_id)
  "sort_order": "desc"          // Sort order (asc, desc)
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "tweets": [
      {
        "id": "uuid-string",
        "tweet_id": "1234567890123456789",
        "cache_complete": true,
        "media_processed": false,
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T11:45:00Z",
        "content_preview": "Tweet content preview..."
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 50,
      "total": 1250,
      "pages": 25
    }
  }
}
```

### GET /v2/tweets/{tweet_id}/detail
**Purpose**: Retrieve comprehensive details for a specific tweet.

**Parameters**:
- `tweet_id` (path): Twitter tweet ID

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "tweet_id": "1234567890123456789",
    "cache_complete": true,
    "media_processed": false,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T11:45:00Z",
    "content_data": {
      "text": "Full tweet content...",
      "user": {
        "screen_name": "username",
        "followers_count": 1000
      },
      "media": [],
      "entities": {}
    },
    "queue_status": {
      "status": "processed",
      "priority": 0,
      "created_at": "2024-01-15T10:30:00Z",
      "processed_at": "2024-01-15T11:45:00Z"
    }
  }
}
```

### POST /v2/tweets/{tweet_id}/update-flags
**Purpose**: Update specific processing flags for a tweet.

**Request Body**:
```json
{
  "cache_complete": true,
  "media_processed": false,
  "force_update": false
}
```

**Response**:
```json
{
  "success": true,
  "message": "Tweet flags updated successfully",
  "data": {
    "tweet_id": "1234567890123456789",
    "updated_flags": {
      "cache_complete": true,
      "media_processed": false
    },
    "updated_at": "2024-01-15T12:00:00Z"
  }
}
```

### POST /v2/tweets/{tweet_id}/reprocess
**Purpose**: Trigger reprocessing for a specific tweet.

**Request Body**:
```json
{
  "reprocess_type": "pipeline",  // "pipeline" or "full"
  "reset_flags": ["cache_complete", "media_processed"],
  "priority": 1
}
```

**Response**:
```json
{
  "success": true,
  "message": "Tweet queued for reprocessing",
  "data": {
    "tweet_id": "1234567890123456789",
    "reprocess_type": "pipeline",
    "queue_position": 15,
    "estimated_processing_time": "5 minutes"
  }
}
```

### POST /v2/tweets/bulk-operations
**Purpose**: Perform bulk operations on multiple tweets.

**Request Body**:
```json
{
  "operation": "update_flags",   // "update_flags", "reprocess", "delete"
  "tweet_ids": ["tweet1", "tweet2", "tweet3"],
  "operation_data": {
    "flags": {
      "cache_complete": true,
      "media_processed": false
    },
    "reprocess_type": "pipeline"
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Bulk operation completed",
  "data": {
    "operation": "update_flags",
    "total_tweets": 3,
    "successful": 2,
    "failed": 1,
    "results": [
      {
        "tweet_id": "tweet1",
        "success": true,
        "message": "Updated successfully"
      },
      {
        "tweet_id": "tweet2",
        "success": true,
        "message": "Updated successfully"
      },
      {
        "tweet_id": "tweet3",
        "success": false,
        "error": "Tweet not found"
      }
    ]
  }
}
```

### GET /v2/tweets/statistics
**Purpose**: Retrieve comprehensive tweet processing statistics.

**Response**:
```json
{
  "success": true,
  "data": {
    "tweet_cache": {
      "total_tweets": 15000,
      "cache_complete": 12000,
      "cache_incomplete": 3000,
      "cache_completion_rate": 80.0
    },
    "media_processing": {
      "total_tweets": 15000,
      "media_processed": 10000,
      "media_pending": 5000,
      "processing_rate": 66.7
    },
    "processing_queue": {
      "unprocessed": 450,
      "processed": 14550,
      "failed": 0,
      "queue_health": "healthy"
    },
    "categories": {
      "total_categories": 25,
      "active_categories": 23,
      "items_categorized": 8500
    },
    "performance": {
      "avg_processing_time": 2.5,
      "throughput_per_hour": 600,
      "last_updated": "2024-01-15T12:00:00Z"
    }
  }
}
```

### GET /v2/tweets/categories
**Purpose**: Retrieve available categories for filtering.

**Response**:
```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "main_category": "Technology",
        "sub_categories": [
          {
            "sub_category": "AI/ML",
            "item_count": 250,
            "is_active": true
          },
          {
            "sub_category": "Web Development",
            "item_count": 180,
            "is_active": true
          }
        ]
      }
    ],
    "total_main_categories": 8,
    "total_sub_categories": 32
  }
}
```

## Backup and Recovery API

### POST /backup/create
**Purpose**: Create a new backup of the system.

**Request Body**:
```json
{
  "backup_id": "manual_backup_20240115",
  "include_database": true,
  "include_json_files": true,
  "include_media": false,
  "include_logs": true,
  "description": "Pre-maintenance backup"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Backup created successfully",
  "data": {
    "backup_id": "manual_backup_20240115",
    "backup_path": "/backups/manual_backup_20240115",
    "components": {
      "database": {
        "size": "150MB",
        "checksum": "abc123def456"
      },
      "json_files": {
        "size": "25MB", 
        "checksum": "def456ghi789"
      },
      "logs": {
        "size": "10MB",
        "checksum": "ghi789jkl012"
      }
    },
    "total_size": "185MB",
    "duration": "45 seconds",
    "created_at": "2024-01-15T12:00:00Z"
  }
}
```

### GET /backup/list
**Purpose**: List all available backups with filtering and pagination.

**Parameters**:
```json
{
  "page": 1,
  "per_page": 20,
  "backup_type": "automated",     // "automated", "manual", "pre_migration"
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "backups": [
      {
        "backup_id": "auto_backup_20240115_120000",
        "backup_type": "automated",
        "components": ["database", "json_files"],
        "total_size": "175MB",
        "created_at": "2024-01-15T12:00:00Z",
        "retention_until": "2024-02-15T12:00:00Z",
        "is_valid": true
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 45,
      "pages": 3
    }
  }
}
```

### GET /backup/{backup_id}
**Purpose**: Get detailed information about a specific backup.

**Response**:
```json
{
  "success": true,
  "data": {
    "backup_id": "auto_backup_20240115_120000",
    "backup_type": "automated",
    "description": "Daily automated backup",
    "created_at": "2024-01-15T12:00:00Z",
    "retention_until": "2024-02-15T12:00:00Z",
    "components": {
      "database": {
        "file_path": "/backups/auto_backup_20240115_120000/database.sql",
        "size": "150MB",
        "checksum": "abc123def456",
        "is_valid": true
      },
      "json_files": {
        "file_path": "/backups/auto_backup_20240115_120000/json_files.tar.gz",
        "size": "25MB",
        "checksum": "def456ghi789", 
        "is_valid": true
      }
    },
    "metadata": {
      "agent_version": "1.0.0",
      "database_version": "12.8",
      "backup_tool_version": "1.0.0"
    },
    "total_size": "175MB",
    "is_valid": true
  }
}
```

### POST /backup/{backup_id}/validate
**Purpose**: Validate backup integrity.

**Response**:
```json
{
  "success": true,
  "data": {
    "backup_id": "auto_backup_20240115_120000",
    "validation_result": {
      "is_valid": true,
      "components": {
        "database": {
          "checksum_valid": true,
          "file_exists": true,
          "sql_syntax_valid": true
        },
        "json_files": {
          "checksum_valid": true,
          "file_exists": true,
          "archive_valid": true
        }
      },
      "validation_time": "2024-01-15T13:00:00Z",
      "validation_duration": "15 seconds"
    }
  }
}
```

### POST /backup/{backup_id}/restore
**Purpose**: Restore system from backup.

**Request Body**:
```json
{
  "components": ["database", "json_files"],
  "create_rollback_backup": true,
  "force_restore": false
}
```

**Response**:
```json
{
  "success": true,
  "message": "Restore completed successfully",
  "data": {
    "backup_id": "auto_backup_20240115_120000",
    "restored_components": ["database", "json_files"],
    "rollback_backup_id": "rollback_20240115_130000",
    "restore_duration": "3 minutes",
    "restored_at": "2024-01-15T13:05:00Z"
  }
}
```

### DELETE /backup/{backup_id}
**Purpose**: Delete a specific backup.

**Response**:
```json
{
  "success": true,
  "message": "Backup deleted successfully",
  "data": {
    "backup_id": "old_backup_20240101_120000",
    "freed_space": "180MB",
    "deleted_at": "2024-01-15T14:00:00Z"
  }
}
```

### POST /backup/cleanup
**Purpose**: Trigger cleanup of expired backups.

**Request Body**:
```json
{
  "dry_run": false,
  "force_cleanup": false
}
```

**Response**:
```json
{
  "success": true,
  "message": "Backup cleanup completed",
  "data": {
    "expired_backups": 5,
    "freed_space": "900MB",
    "cleanup_duration": "30 seconds",
    "deleted_backup_ids": [
      "old_backup_20231215_120000",
      "old_backup_20231220_120000"
    ]
  }
}
```

### GET /backup/statistics
**Purpose**: Get backup system statistics.

**Response**:
```json
{
  "success": true,
  "data": {
    "total_backups": 45,
    "backup_types": {
      "automated": 40,
      "manual": 3,
      "pre_migration": 2
    },
    "total_storage_used": "8.2GB",
    "average_backup_size": "180MB",
    "oldest_backup": "2023-12-01T12:00:00Z",
    "newest_backup": "2024-01-15T12:00:00Z",
    "retention_stats": {
      "daily_retention": 30,
      "weekly_retention": 12,
      "monthly_retention": 6
    },
    "health": {
      "last_automated_backup": "2024-01-15T12:00:00Z",
      "failed_backups_last_week": 0,
      "backup_system_status": "healthy"
    }
  }
}
```

## Migration API

### POST /migration/execute
**Purpose**: Execute the JSON to Database migration.

**Request Body**:
```json
{
  "migration_id": "migration_20240115_150000",
  "validate_only": false,
  "force_migration": false,
  "skip_backup": false
}
```

**Response**:
```json
{
  "success": true,
  "message": "Migration completed successfully",
  "data": {
    "migration_id": "migration_20240115_150000",
    "pre_migration_backup_id": "pre_migration_20240115_150000",
    "results": {
      "tweet_cache": {
        "success": true,
        "records_migrated": 15000,
        "duration_seconds": 45.2,
        "errors": []
      },
      "processing_queues": {
        "success": true,
        "records_migrated": 500,
        "duration_seconds": 5.1,
        "errors": []
      }
    },
    "total_duration": "1 minute 30 seconds",
    "validation_passed": true,
    "completed_at": "2024-01-15T15:05:00Z"
  }
}
```

### POST /migration/validate
**Purpose**: Validate migration without executing.

**Response**:
```json
{
  "success": true,
  "data": {
    "validation_results": {
      "json_files": {
        "tweet_cache.json": {
          "exists": true,
          "valid_format": true,
          "record_count": 15000
        },
        "categories.json": {
          "exists": true,
          "valid_format": true,
          "record_count": 25
        }
      },
      "database": {
        "connection_valid": true,
        "schema_exists": true,
        "tables_exist": true
      }
    },
    "migration_ready": true,
    "estimated_duration": "2 minutes",
    "potential_issues": []
  }
}
```

### POST /migration/rollback
**Purpose**: Rollback migration to previous state.

**Request Body**:
```json
{
  "backup_id": "pre_migration_20240115_150000",
  "confirm_rollback": true
}
```

**Response**:
```json
{
  "success": true,
  "message": "Migration rollback completed",
  "data": {
    "restored_backup_id": "pre_migration_20240115_150000",
    "rollback_duration": "2 minutes",
    "restored_components": ["database", "json_files"],
    "completed_at": "2024-01-15T16:00:00Z"
  }
}
```

## Response Format

### Standard Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data specific to endpoint
  },
  "meta": {
    "request_id": "uuid-string",
    "timestamp": "2024-01-15T12:00:00Z",
    "version": "v2",
    "processing_time": "150ms"
  }
}
```

### Standard Error Response
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "per_page",
      "value": 500,
      "constraint": "Maximum value is 200"
    }
  },
  "meta": {
    "request_id": "uuid-string",
    "timestamp": "2024-01-15T12:00:00Z",
    "version": "v2"
  }
}
```

## Error Handling

### HTTP Status Codes
- **200**: Success
- **201**: Created
- **400**: Bad Request (validation errors)
- **401**: Unauthorized
- **403**: Forbidden
- **404**: Not Found
- **409**: Conflict (duplicate resource)
- **429**: Too Many Requests (rate limiting)
- **500**: Internal Server Error

### Common Error Codes
- `VALIDATION_ERROR`: Request validation failed
- `RESOURCE_NOT_FOUND`: Requested resource does not exist
- `DUPLICATE_RESOURCE`: Resource already exists
- `OPERATION_FAILED`: Operation could not be completed
- `BACKUP_ERROR`: Backup operation failed
- `MIGRATION_ERROR`: Migration operation failed
- `DATABASE_ERROR`: Database operation failed

### Error Response Examples

**Validation Error (400)**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "per_page": "Value must be between 1 and 200",
      "sort_field": "Must be one of: created_at, updated_at, tweet_id"
    }
  }
}
```

**Resource Not Found (404)**:
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Tweet not found",
    "details": {
      "tweet_id": "nonexistent_tweet_123"
    }
  }
}
```

**Rate Limiting (429)**:
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 100,
      "window": "1 hour",
      "retry_after": 3600
    }
  }
}
```

## Rate Limiting

### Current Limits
- **General API**: 1000 requests/hour per IP
- **Bulk Operations**: 10 requests/hour per IP
- **Backup Operations**: 5 requests/hour per IP
- **Migration Operations**: 1 request/hour per IP

### Headers
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1642248000
```

## API Examples

### Python Client Example
```python
import requests
import json

class KnowledgeBaseAPIClient:
    def __init__(self, base_url, session_token=None):
        self.base_url = base_url
        self.session = requests.Session()
        if session_token:
            self.session.headers.update({
                'Authorization': f'Bearer {session_token}'
            })
    
    def explore_tweets(self, page=1, per_page=50, search=None, filters=None):
        """Explore tweets with pagination and filtering"""
        params = {
            'page': page,
            'per_page': per_page
        }
        
        if search:
            params['search'] = search
        
        if filters:
            params.update(filters)
        
        response = self.session.get(
            f"{self.base_url}/v2/tweets/explore",
            params=params
        )
        
        return response.json()
    
    def get_tweet_detail(self, tweet_id):
        """Get detailed tweet information"""
        response = self.session.get(
            f"{self.base_url}/v2/tweets/{tweet_id}/detail"
        )
        
        return response.json()
    
    def bulk_update_flags(self, tweet_ids, flags):
        """Update flags for multiple tweets"""
        payload = {
            'operation': 'update_flags',
            'tweet_ids': tweet_ids,
            'operation_data': {
                'flags': flags
            }
        }
        
        response = self.session.post(
            f"{self.base_url}/v2/tweets/bulk-operations",
            json=payload
        )
        
        return response.json()
    
    def create_backup(self, backup_id=None, include_media=False):
        """Create system backup"""
        payload = {
            'include_database': True,
            'include_json_files': True,
            'include_media': include_media,
            'include_logs': True
        }
        
        if backup_id:
            payload['backup_id'] = backup_id
        
        response = self.session.post(
            f"{self.base_url}/backup/create",
            json=payload
        )
        
        return response.json()

# Usage example
client = KnowledgeBaseAPIClient('http://localhost:5000')

# Search for tweets
tweets = client.explore_tweets(
    search='machine learning',
    filters={'cache_complete': True},
    per_page=25
)

# Get tweet details
detail = client.get_tweet_detail('1234567890123456789')

# Update multiple tweets
result = client.bulk_update_flags(
    tweet_ids=['tweet1', 'tweet2', 'tweet3'],
    flags={'media_processed': True}
)

# Create backup
backup = client.create_backup(
    backup_id='api_test_backup',
    include_media=False
)
```

### JavaScript/Node.js Example
```javascript
class KnowledgeBaseAPIClient {
    constructor(baseUrl, sessionToken = null) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json'
        };
        
        if (sessionToken) {
            this.headers['Authorization'] = `Bearer ${sessionToken}`;
        }
    }
    
    async request(method, endpoint, data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const options = {
            method,
            headers: this.headers
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        return await response.json();
    }
    
    async exploreTweets(options = {}) {
        const params = new URLSearchParams(options);
        return this.request('GET', `/v2/tweets/explore?${params}`);
    }
    
    async getTweetDetail(tweetId) {
        return this.request('GET', `/v2/tweets/${tweetId}/detail`);
    }
    
    async bulkUpdateFlags(tweetIds, flags) {
        const payload = {
            operation: 'update_flags',
            tweet_ids: tweetIds,
            operation_data: { flags }
        };
        
        return this.request('POST', '/v2/tweets/bulk-operations', payload);
    }
    
    async createBackup(options = {}) {
        const payload = {
            include_database: true,
            include_json_files: true,
            include_media: false,
            include_logs: true,
            ...options
        };
        
        return this.request('POST', '/backup/create', payload);
    }
}

// Usage
const client = new KnowledgeBaseAPIClient('http://localhost:5000');

// Search tweets
const tweets = await client.exploreTweets({
    search: 'artificial intelligence',
    cache_complete: true,
    per_page: 20
});

// Get statistics
const stats = await client.request('GET', '/v2/tweets/statistics');

// Create backup
const backup = await client.createBackup({
    backup_id: 'manual_backup_js',
    description: 'Backup created via JavaScript client'
});
```

---

**API Status**: ✅ Complete - All endpoints implemented and documented
**Next Steps**: Client library development and integration testing 