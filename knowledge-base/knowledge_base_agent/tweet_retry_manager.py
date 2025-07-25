"""
Tweet Retry Management System

Handles automatic retry logic for failed tweets with intelligent strategies,
exponential backoff, and comprehensive error analysis.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
import json


class RetryStrategy(Enum):
    """Different retry strategies for different types of failures."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    IMMEDIATE = "immediate"
    NO_RETRY = "no_retry"


class FailureType(Enum):
    """Classification of failure types for intelligent retry strategies."""
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    TEMPORARY_ERROR = "temporary_error"
    CONFIGURATION_ERROR = "configuration_error"
    DATA_ERROR = "data_error"
    PERMANENT_ERROR = "permanent_error"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 300.0  # 5 minutes
    exponential_factor: float = 2.0
    jitter: bool = True
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF


@dataclass
class RetryAttempt:
    """Record of a retry attempt."""
    attempt_number: int
    timestamp: datetime
    error_message: str
    failure_type: FailureType
    retry_after: Optional[datetime] = None


class TweetRetryManager:
    """
    Manages retry logic for failed tweet processing operations.
    
    Features:
    - Intelligent failure type classification
    - Multiple retry strategies
    - Exponential backoff with jitter
    - Retry attempt tracking and analysis
    - Circuit breaker pattern for persistent failures
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(__name__)
        self._retry_history: Dict[str, List[RetryAttempt]] = {}
        self._circuit_breakers: Dict[str, datetime] = {}  # tweet_id -> circuit_open_until
        
    def should_retry(self, tweet_id: str, tweet_data: Dict[str, Any], error: Optional[Exception] = None) -> bool:
        """
        Determine if a tweet should be retried based on its state and error history.
        
        Args:
            tweet_id: The tweet ID to check
            tweet_data: Current tweet data with error information
            error: Optional exception that caused the failure
            
        Returns:
            True if the tweet should be retried, False otherwise
        """
        # Check circuit breaker
        if self._is_circuit_open(tweet_id):
            self.logger.debug(f"Circuit breaker open for tweet {tweet_id}, skipping retry")
            return False
        
        # Get current retry count
        retry_count = self._get_retry_count(tweet_id, tweet_data)
        
        if retry_count >= self.config.max_retries:
            self.logger.info(f"Tweet {tweet_id} exceeded max retries ({self.config.max_retries})")
            return False
        
        # Analyze failure type to determine if retry is appropriate
        failure_type = self._classify_failure(tweet_data, error)
        
        if failure_type == FailureType.PERMANENT_ERROR:
            self.logger.info(f"Tweet {tweet_id} has permanent error, not retrying")
            return False
        
        # Check if enough time has passed since last retry
        if not self._can_retry_now(tweet_id, failure_type):
            return False
        
        return True
    
    def schedule_retry(self, tweet_id: str, tweet_data: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """
        Schedule a retry for a failed tweet and update its retry metadata.
        
        Args:
            tweet_id: The tweet ID to retry
            tweet_data: Current tweet data
            error: The exception that caused the failure
            
        Returns:
            Updated tweet data with retry information
        """
        failure_type = self._classify_failure(tweet_data, error)
        retry_count = self._get_retry_count(tweet_id, tweet_data)
        next_retry_count = retry_count + 1
        
        # Calculate next retry time
        delay = self._calculate_delay(next_retry_count, failure_type)
        next_retry_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
        
        # Record retry attempt
        attempt = RetryAttempt(
            attempt_number=next_retry_count,
            timestamp=datetime.now(timezone.utc),
            error_message=str(error),
            failure_type=failure_type,
            retry_after=next_retry_time
        )
        
        if tweet_id not in self._retry_history:
            self._retry_history[tweet_id] = []
        self._retry_history[tweet_id].append(attempt)
        
        # Update tweet data with retry information
        updated_data = tweet_data.copy()
        updated_data.update({
            'retry_count': next_retry_count,
            'last_retry_attempt': datetime.now(timezone.utc).isoformat(),
            'next_retry_after': next_retry_time.isoformat(),
            'failure_type': failure_type.value,
            'retry_strategy': self.config.retry_strategy.value,
            'retry_history': json.dumps([
                {
                    'attempt': a.attempt_number,
                    'timestamp': a.timestamp.isoformat(),
                    'error': a.error_message,
                    'failure_type': a.failure_type.value
                }
                for a in self._retry_history[tweet_id]
            ])
        })
        
        self.logger.info(f"Scheduled retry {next_retry_count}/{self.config.max_retries} for tweet {tweet_id} "
                        f"(failure: {failure_type.value}, delay: {delay:.1f}s)")
        
        return updated_data
    
    def get_retryable_tweets(self, tweets_data_map: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Get list of tweet IDs that are ready for retry.
        
        Args:
            tweets_data_map: Map of tweet ID to tweet data
            
        Returns:
            List of tweet IDs ready for retry
        """
        retryable = []
        current_time = datetime.now(timezone.utc)
        
        for tweet_id, tweet_data in tweets_data_map.items():
            # Check if tweet has any errors
            has_errors = any([
                tweet_data.get('_cache_error'),
                tweet_data.get('_media_error'),
                tweet_data.get('_llm_error'),
                tweet_data.get('_kbitem_error'),
                tweet_data.get('_db_error')
            ])
            
            if not has_errors:
                continue
            
            # Check if tweet is eligible for retry
            if not self.should_retry(tweet_id, tweet_data):
                continue
            
            # Check if retry time has arrived
            next_retry_str = tweet_data.get('next_retry_after')
            if next_retry_str:
                try:
                    next_retry_time = datetime.fromisoformat(next_retry_str.replace('Z', '+00:00'))
                    if current_time < next_retry_time:
                        continue
                except (ValueError, AttributeError):
                    pass  # Invalid timestamp, allow retry
            
            retryable.append(tweet_id)
        
        return retryable
    
    def clear_retry_metadata(self, tweet_id: str, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clear retry metadata from tweet data after successful processing.
        
        Args:
            tweet_id: The tweet ID
            tweet_data: Current tweet data
            
        Returns:
            Updated tweet data with retry metadata cleared
        """
        updated_data = tweet_data.copy()
        
        # Remove retry-related fields
        retry_fields = [
            'retry_count', 'last_retry_attempt', 'next_retry_after',
            'failure_type', 'retry_strategy', 'retry_history'
        ]
        
        for field in retry_fields:
            updated_data.pop(field, None)
        
        # Clear error flags
        error_fields = [
            '_cache_error', '_media_error', '_llm_error', 
            '_kbitem_error', '_db_error'
        ]
        
        for field in error_fields:
            updated_data.pop(field, None)
        
        # Clear from retry history
        if tweet_id in self._retry_history:
            del self._retry_history[tweet_id]
        
        # Clear circuit breaker
        if tweet_id in self._circuit_breakers:
            del self._circuit_breakers[tweet_id]
        
        self.logger.info(f"Cleared retry metadata for successfully processed tweet {tweet_id}")
        return updated_data
    
    def _get_retry_count(self, tweet_id: str, tweet_data: Dict[str, Any]) -> int:
        """Get current retry count for a tweet."""
        return tweet_data.get('retry_count', 0)
    
    def _classify_failure(self, tweet_data: Dict[str, Any], error: Optional[Exception] = None) -> FailureType:
        """
        Classify the type of failure based on error information.
        
        Args:
            tweet_data: Tweet data containing error information
            error: Optional exception object
            
        Returns:
            Classified failure type
        """
        # Check error messages for classification
        error_messages = []
        
        for error_field in ['_cache_error', '_media_error', '_llm_error', '_kbitem_error', '_db_error']:
            if tweet_data.get(error_field):
                error_messages.append(tweet_data[error_field].lower())
        
        if error:
            error_messages.append(str(error).lower())
        
        error_text = ' '.join(error_messages)
        
        # Network-related errors
        if any(keyword in error_text for keyword in ['connection', 'timeout', 'network', 'dns', 'socket']):
            return FailureType.NETWORK_ERROR
        
        # Rate limiting
        if any(keyword in error_text for keyword in ['rate limit', 'too many requests', '429', 'throttle']):
            return FailureType.RATE_LIMIT
        
        # Configuration errors
        if any(keyword in error_text for keyword in ['config', 'permission', 'auth', 'forbidden', '401', '403']):
            return FailureType.CONFIGURATION_ERROR
        
        # Data-related errors
        if any(keyword in error_text for keyword in ['json', 'parse', 'format', 'encoding', 'validation']):
            return FailureType.DATA_ERROR
        
        # Permanent errors
        if any(keyword in error_text for keyword in ['not found', '404', 'deleted', 'suspended', 'permanent']):
            return FailureType.PERMANENT_ERROR
        
        # Default to temporary error for unknown issues
        return FailureType.TEMPORARY_ERROR
    
    def _calculate_delay(self, attempt_number: int, failure_type: FailureType) -> float:
        """
        Calculate delay before next retry attempt.
        
        Args:
            attempt_number: Current attempt number (1-based)
            failure_type: Type of failure
            
        Returns:
            Delay in seconds
        """
        if failure_type == FailureType.RATE_LIMIT:
            # Longer delays for rate limiting
            base_delay = self.config.base_delay * 10
        else:
            base_delay = self.config.base_delay
        
        if self.config.retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (self.config.exponential_factor ** (attempt_number - 1))
        elif self.config.retry_strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * attempt_number
        else:  # IMMEDIATE
            delay = 0
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter and delay > 0:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor
        
        return delay
    
    def _can_retry_now(self, tweet_id: str, failure_type: FailureType) -> bool:
        """Check if enough time has passed to retry."""
        if tweet_id not in self._retry_history:
            return True
        
        last_attempt = self._retry_history[tweet_id][-1]
        if not last_attempt.retry_after:
            return True
        
        return datetime.now(timezone.utc) >= last_attempt.retry_after
    
    def _is_circuit_open(self, tweet_id: str) -> bool:
        """Check if circuit breaker is open for a tweet."""
        if tweet_id not in self._circuit_breakers:
            return False
        
        return datetime.now(timezone.utc) < self._circuit_breakers[tweet_id]
    
    def open_circuit_breaker(self, tweet_id: str, duration_minutes: int = 60):
        """Open circuit breaker for a tweet to prevent immediate retries."""
        open_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        self._circuit_breakers[tweet_id] = open_until
        self.logger.warning(f"Opened circuit breaker for tweet {tweet_id} until {open_until}")
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get comprehensive retry statistics for monitoring."""
        stats = {
            'total_tweets_with_retries': len(self._retry_history),
            'active_circuit_breakers': len([
                tweet_id for tweet_id, open_until in self._circuit_breakers.items()
                if datetime.now(timezone.utc) < open_until
            ]),
            'failure_type_distribution': {},
            'retry_count_distribution': {},
            'average_retries_per_tweet': 0
        }
        
        if not self._retry_history:
            return stats
        
        # Analyze failure types
        failure_counts = {}
        total_retries = 0
        
        for attempts in self._retry_history.values():
            total_retries += len(attempts)
            for attempt in attempts:
                failure_type = attempt.failure_type.value
                failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
        
        stats['failure_type_distribution'] = failure_counts
        stats['average_retries_per_tweet'] = total_retries / len(self._retry_history)
        
        # Retry count distribution
        for attempts in self._retry_history.values():
            count = len(attempts)
            stats['retry_count_distribution'][count] = stats['retry_count_distribution'].get(count, 0) + 1
        
        return stats 