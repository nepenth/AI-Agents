from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import List

@dataclass
class ProcessingStats:
    start_time: datetime
    processed_count: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    media_processed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    network_errors: int = 0
    retry_count: int = 0
    processing_times: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'start_time': self.start_time.isoformat(),
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'skipped_count': self.skipped_count,
            'success_rate': f"{(self.success_count / self.processed_count * 100):.1f}%" if self.processed_count else "0%",
            'cache_hit_rate': f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%",
            'error_rate': f"{(self.error_count / self.processed_count * 100):.1f}%",
            'average_retries': self.retry_count / self.processed_count if self.processed_count else 0
        }

    def save_report(self, output_path: Path) -> None:
        report = self.to_dict()
        report['duration'] = str(datetime.now() - self.start_time)
        with output_path.open('w') as f:
            json.dump(report, f, indent=2)

    def get_performance_metrics(self) -> dict:
        metrics = {
            'cache_hit_rate': f"{(self.cache_hits / (self.cache_hits + self.cache_misses) * 100):.1f}%",
            'error_rate': f"{(self.error_count / self.processed_count * 100):.1f}%",
            'average_retries': self.retry_count / self.processed_count if self.processed_count else 0
        }
        if self.processing_times:
            metrics.update({
                'avg_processing_time': f"{sum(self.processing_times) / len(self.processing_times):.2f}s",
                'max_processing_time': f"{max(self.processing_times):.2f}s",
                'min_processing_time': f"{min(self.processing_times):.2f}s"
            })
        return metrics

    def add_processing_time(self, duration: float) -> None:
        self.processing_times.append(duration) 
        