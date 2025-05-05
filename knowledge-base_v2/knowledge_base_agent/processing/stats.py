import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, DefaultDict, List, Tuple

logger = logging.getLogger(__name__)

class ProcessingStats:
    """Tracks statistics during an agent pipeline run."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Resets all statistics for a new run."""
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.run_active: bool = False
        self.counters: DefaultDict[str, int] = defaultdict(int)
        # Store errors as (phase_name, tweet_id or None, error_message)
        self.errors: List[Tuple[str, Optional[str], str]] = []
        # Store timings as (phase_name, duration_seconds)
        self.timings: DefaultDict[str, List[float]] = defaultdict(list)
        self.phase_counts = defaultdict(lambda: {"entered": 0, "success": 0, "failed": 0})
        self.llm_durations = defaultdict(list) # Stores durations for 'interpret', 'categorize', 'generate'
        logger.debug("ProcessingStats reset.")

    def start_run(self):
        """Marks the start of a pipeline run."""
        self.reset()
        self.start_time = time.monotonic()
        self.run_active = True
        logger.info("ProcessingStats run started.")

    def end_run(self):
        """Marks the end of a pipeline run."""
        if self.run_active:
            self.end_time = time.monotonic()
            self.run_active = False
            logger.info(f"ProcessingStats run ended. Duration: {self.get_total_duration():.2f}s")
        else:
            logger.warning("Attempted to end run, but no run was active.")

    def increment_counter(self, name: str, count: int = 1):
        """Increments a named counter."""
        if self.run_active:
            self.counters[name] += count
        else:
            logger.warning(f"Stat counter increment ignored (run not active): {name}")

    def record_error(self, phase: str, tweet_id: Optional[str] = None, error: Optional[Exception] = None, message: Optional[str] = None):
        """Records an error encountered during processing."""
        if self.run_active:
            error_msg = message or str(error) or "Unknown error"
            self.errors.append((phase, tweet_id, error_msg))
            self.increment_counter(f"errors_{phase}")
            self.increment_counter("errors_total")
            logger.debug(f"Recorded error for phase '{phase}', tweet '{tweet_id}': {error_msg[:100]}...") # Log truncated message
        else:
            logger.warning(f"Stat error recording ignored (run not active): {phase}")

    def add_timing(self, name: str, duration_seconds: float):
        """Adds a timing measurement for a specific operation or phase."""
        if self.run_active:
            self.timings[name].append(duration_seconds)
        else:
             logger.warning(f"Stat timing add ignored (run not active): {name}")

    def get_total_duration(self) -> float:
        """Calculates the total duration of the run in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time and self.run_active:
             # Return duration so far if still running
             return time.monotonic() - self.start_time
        return 0.0

    def mark_start(self):
        self.start_time = time.monotonic()

    def mark_end(self):
        self.end_time = time.monotonic()

    def enter_phase(self, phase_name: str):
        self.phase_counts[phase_name]["entered"] += 1

    def finish_phase(self, phase_name: str, success: bool):
        if success:
            self.phase_counts[phase_name]["success"] += 1
        else:
            self.phase_counts[phase_name]["failed"] += 1

    def record_llm_duration(self, phase_name: str, duration: float):
        """Records the duration of an LLM-dependent phase for ETA calculation."""
        if phase_name in ['interpret', 'categorize', 'generate']:
            self.llm_durations[phase_name].append(duration)
        else:
             # Log a warning? Or just ignore? Let's ignore for now.
             pass

    def add_error(self, phase_name: str, error_message: str):
        self.errors.append((phase_name, error_message))

    def get_avg_llm_duration(self, phase_name: str, window: int = 20) -> float | None:
        """Calculates the average duration of the last 'window' LLM calls for a phase."""
        if phase_name not in self.llm_durations or not self.llm_durations[phase_name]:
            return None # Default if no data or phase invalid
        # Simple moving average of the last 'window' durations
        recent_durations = self.llm_durations[phase_name][-window:]
        if not recent_durations:
             return None
        return sum(recent_durations) / len(recent_durations)

    def get_report(self) -> str:
        """Generates a summary report of the processing run."""
        report_lines = ["--- Processing Stats Report ---"]
        total_duration = (self.end_time - self.start_time) if self.end_time else (time.monotonic() - self.start_time)
        report_lines.append(f"Total Run Time: {total_duration:.2f} seconds")

        report_lines.append("\nPhase Summary:")
        for phase, counts in sorted(self.phase_counts.items()):
            report_lines.append(
                f"  - {phase.capitalize()}: "
                f"Entered={counts['entered']}, "
                f"Success={counts['success']}, "
                f"Failed={counts['failed']}"
            )

        report_lines.append("\nAverage LLM Durations (last 20):")
        for phase in ['interpret', 'categorize', 'generate']:
             avg_duration = self.get_avg_llm_duration(phase)
             count = len(self.llm_durations[phase])
             if avg_duration is not None:
                 report_lines.append(f"  - {phase.capitalize()}: {avg_duration:.2f}s (based on {count} samples)")
             else:
                  report_lines.append(f"  - {phase.capitalize()}: No data")


        if self.errors:
            report_lines.append(f"\nErrors Encountered ({len(self.errors)}):")
            for i, (phase, msg) in enumerate(self.errors[:10]): # Show first 10 errors
                report_lines.append(f"  {i+1}. [{phase.capitalize()}] {msg}")
            if len(self.errors) > 10:
                report_lines.append("  ... (more errors logged)")

        report_lines.append("--- End Report ---")
        return "\n".join(report_lines)
