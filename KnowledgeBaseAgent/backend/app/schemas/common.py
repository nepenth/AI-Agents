"""
Common schemas for pagination, search, and filtering.
"""
from typing import Generic, TypeVar, List, Optional, Dict, Any
from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    items: List[T] = Field(description="List of items")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")
    
    @classmethod
    def create(cls, items: List[T], total: int, page: int, size: int) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + size - 1) // size  # Ceiling division
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )


class SearchParams(BaseModel):
    """Search parameters for text-based queries."""
    query: Optional[str] = Field(default=None, description="Search query")
    fields: Optional[List[str]] = Field(default=None, description="Fields to search in")
    
    
class FilterParams(BaseModel):
    """Base filter parameters."""
    created_after: Optional[str] = Field(default=None, description="Filter items created after this date (ISO format)")
    created_before: Optional[str] = Field(default=None, description="Filter items created before this date (ISO format)")
    updated_after: Optional[str] = Field(default=None, description="Filter items updated after this date (ISO format)")
    updated_before: Optional[str] = Field(default=None, description="Filter items updated before this date (ISO format)")


class ErrorResponse(BaseModel):
    """Standard error response format."""
    success: bool = False
    error_code: str = Field(description="Error code identifier")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: str = Field(description="Error timestamp (ISO format)")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")


class SuccessResponse(BaseModel):
    """Standard success response format."""
    success: bool = True
    message: str = Field(description="Success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional response data")
    timestamp: str = Field(description="Response timestamp (ISO format)")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracking")