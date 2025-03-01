from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional
import logging

@dataclass
class ProcessingStats:
    """Track progress of content processing."""
    start_time: datetime = field(default_factory=datetime.now)
    media_processed: int = 0
    categories_processed: int = 0
    processed_count: int = 0
    error_count: int = 0
    readme_generated: bool = False
    success_count: int = 0
    skipped_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    network_errors: int = 0
    retry_count: int = 0
    processing_times: List[float] = field(default_factory=list)
    validation_count: int = 0

    def __init__(self, start_time: datetime):
        self.start_time = start_time
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.media_processed = 0
        self.categories_processed = 0
        self.readme_generated = False
        self.validation_count = 0
        self.skipped_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.network_errors = 0
        self.retry_count = 0
        self.processing_times = []  # Explicitly initialize

    def __str__(self) -> str:
        return (
            f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"Processed: {self.processed_count}, "
            f"Media: {self.media_processed}, "
            f"Categories: {self.categories_processed}, "
            f"Errors: {self.error_count}, "
            f"README Generated: {self.readme_generated}"
        )

    def to_dict(self) -> dict:
        """Convert stats to dictionary format."""
        success_rate = (self.success_count / self.processed_count * 100) if self.processed_count else 0
        cache_hit_rate = (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) if (self.cache_hits + self.cache_misses) > 0 else 0
        error_rate = (self.error_count / self.processed_count * 100) if self.processed_count else 0
        avg_retries = self.retry_count / self.processed_count if self.processed_count else 0
        
        return {
            'start_time': self.start_time.isoformat(),
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'skipped_count': self.skipped_count,
            'media_processed': self.media_processed,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'network_errors': self.network_errors,
            'retry_count': self.retry_count,
            'success_rate': f"{success_rate:.1f}%",
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'error_rate': f"{error_rate:.1f}%",
            'average_retries': f"{avg_retries:.2f}"
        }

    def save_report(self, output_path: Path) -> None:
        """Save stats report to a JSON file."""
        try:
            report = self.to_dict()
            report['duration'] = str(datetime.now() - self.start_time)
            with output_path.open('w') as f:
                json.dump(report, f, indent=2)
            logging.debug(f"Saved stats report to {output_path}")
        except Exception as e:
            logging.error(f"Failed to save stats report: {e}")

    def get_performance_metrics(self) -> dict:
        """Generate performance metrics."""
        metrics = {
            'cache_hit_rate': "N/A" if (self.cache_hits + self.cache_misses) == 0 else f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%",
            'error_rate': f"{(self.error_count / self.processed_count * 100):.1f}%" if self.processed_count else "0.0%",
            'average_retries': self.retry_count / self.processed_count if self.processed_count else 0
        }
        if self.processing_times:  # Check if list is populated
            metrics.update({
                'avg_processing_time': f"{sum(self.processing_times) / len(self.processing_times):.2f}s",
                'max_processing_time': f"{max(self.processing_times):.2f}s",
                'min_processing_time': f"{min(self.processing_times):.2f}s"
            })
        return metrics

    def add_processing_time(self, duration: float) -> None:
        """Add processing time for a single operation."""
        self.processing_times.append(duration)

@dataclass
class ProcessingResult:
    """Results of a knowledge base agent run."""
    stats: ProcessingStats
    readme_generated: bool = False
    readme_path: Optional[Path] = None
    readme_generation_method: str = "none"  # "intelligent", "static", or "none"
    
    def __str__(self) -> str:
        return (
            f"Processing completed:\n"
            f"{self.stats}\n"
            f"README Generated: {self.readme_generated} (Method: {self.readme_generation_method})"
        )