from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

@dataclass
class ProcessingStats:
    start_time: datetime
    processed_count: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0

    def to_dict(self) -> dict:
        return {
            'start_time': self.start_time.isoformat(),
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'skipped_count': self.skipped_count,
            'success_rate': f"{(self.success_count / self.processed_count * 100):.1f}%" if self.processed_count else "0%"
        }

    def save_report(self, output_path: Path) -> None:
        report = self.to_dict()
        report['duration'] = str(datetime.now() - self.start_time)
        with output_path.open('w') as f:
            json.dump(report, f, indent=2) 