import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, DefaultDict, List, Tuple, Set

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
        # Store errors as (phase_name, tweet_id or None, error_message, exception_object)
        self.errors: List[Tuple[str, Optional[str], str, Optional[Exception]]] = []
        # Store timings as (phase_name, duration_seconds)
        self.timings: DefaultDict[str, List[float]] = defaultdict(list)
        # New structure for phase_counts
        self.phase_counts = defaultdict(lambda: {
            "orchestration_entries": 0, # How many times the phase block was entered
            "orchestration_completions": 0, # How many times the phase block completed successfully
            "orchestration_failures": 0,  # How many times the phase block failed to complete
            "items_attempted": 0,    # Total items for which processing was attempted in this phase
            "items_succeeded": 0,    # Items that succeeded processing in this phase
            "items_failed": 0        # Items that failed processing in this phase
        })
        self.llm_durations = defaultdict(list) # Stores durations for 'interpret', 'categorize', 'generate'
        self.total_items_in_run: int = 0
        self.items_processed_overall_distinct: Set[str] = set() # Track distinct items processed across all phases
        self.total_phases_for_run: int = 0 # Total phases planned for this run
        self.current_phase_number: int = 0 # Current phase number being executed
        self.current_batch_total_items: int = 0 # Items in the current phase's batch
        self.current_batch_processed_count: int = 0 # Items processed in current batch
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
        if self.start_time is not None:
            self.counters[name] += count
        else:
            logger.warning(f"Stat counter increment ignored (run not started): {name}")

    def set_counter(self, name: str, value: int):
        """Sets a named counter to a specific value."""
        if self.start_time is not None:
            self.counters[name] = value
        else:
            logger.warning(f"Stat counter set ignored (run not started): {name}")

    def record_error(self, phase: str, tweet_id: Optional[str] = None, error: Optional[Exception] = None, message: Optional[str] = None):
        """Records a general error, often tied to phase orchestration or run-level issues."""
        if self.start_time is not None:
            error_msg = message or str(error) or "Unknown error"
            self.errors.append((phase, tweet_id, error_msg, error))
            # This method is more for non-item specific phase failures or general errors.
            # Item-specific failures are now primarily counted in record_item_processed.
            # We might still want to increment a general error counter here.
            self.counters["errors_total"] += 1
            logger.debug(f"Recorded general error for phase \'{phase}\', tweet \'{tweet_id}\': {error_msg[:100]}...")
        else:
            logger.warning(f"Stat error recording ignored (run not started): {phase}")

    def add_timing(self, name: str, duration_seconds: float):
        """Adds a timing measurement for a specific operation or phase."""
        if self.start_time is not None:
            self.timings[name].append(duration_seconds)
        else:
             logger.warning(f"Stat timing add ignored (run not started): {name}")

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

    def enter_phase(self, phase_name: str, current_phase_num: int, total_phases_in_run: int):
        self.phase_counts[phase_name]["orchestration_entries"] += 1
        self.current_phase_name = phase_name
        self.current_phase_number = current_phase_num
        self.total_phases_for_run = total_phases_in_run
        self.current_batch_total_items = 0
        self.current_batch_processed_count = 0

    def finish_phase(self, phase_name: str, orchestration_success: bool):
        """Marks the completion of a phase's orchestration block."""
        if orchestration_success:
            self.phase_counts[phase_name]["orchestration_completions"] += 1
        else:
            self.phase_counts[phase_name]["orchestration_failures"] += 1
            # If orchestration failed, we might also call record_error here
            # self.record_error(phase_name, message="Phase orchestration failed.")

    def record_llm_duration(self, phase_name: str, duration: float):
        """Records the duration of an LLM-dependent phase for ETA calculation."""
        if phase_name in ['interpret', 'categorize', 'generate']:
            self.llm_durations[phase_name].append(duration)
        else:
             pass

    def add_error(self, phase_name: str, error_message: str, tweet_id: Optional[str] = None, exception_obj: Optional[Exception] = None):
        # Consolidate error recording to record_error or ensure this has a distinct purpose.
        # This seems duplicative of record_error if not carefully managed.
        # For now, let's assume record_error is the primary method for general errors.
        self.errors.append((phase_name, tweet_id, error_message, exception_obj))

    def get_avg_llm_duration(self, phase_name: str, window: int = 20) -> float | None:
        """Calculates the average duration of the last 'window' LLM calls for a phase."""
        if phase_name not in self.llm_durations or not self.llm_durations[phase_name]:
            return None
        recent_durations = self.llm_durations[phase_name][-window:]
        if not recent_durations:
             return None
        return sum(recent_durations) / len(recent_durations)

    def set_total_items_to_process(self, count: int):
        self.total_items_in_run = count

    def set_current_batch_total(self, count: int):
        self.current_batch_total_items = count
        self.current_batch_processed_count = 0

    def increment_batch_processed(self, item_id: str):
        # This method is specific to batch progress, distinct from overall item success/failure recording
        self.current_batch_processed_count += 1
        self.items_processed_overall_distinct.add(item_id) # Still add to distinct set here

    def record_item_processed(self, phase_name: str, duration: float, error: bool = False, error_details: Optional[str] = None, item_id: Optional[str] = None):
        self.phase_counts[phase_name]["items_attempted"] += 1
        if item_id:
            # Call increment_batch_processed to update batch counts and overall distinct set
            self.increment_batch_processed(item_id)
            logger.debug(f"Stats: record_item_processed for item_id='{item_id}', phase='{phase_name}'. Distinct items set size: {len(self.items_processed_overall_distinct)}, Content: {self.items_processed_overall_distinct}")
        
        if error:
            self.phase_counts[phase_name]["items_failed"] += 1
            if error_details and item_id: # Log item-specific errors to the main error list for visibility
                self.errors.append((phase_name, item_id, error_details, None)) # Add None for exception_obj if not available directly
                self.counters["errors_total"] += 1 # Ensure total errors counter is updated
        else:
            self.phase_counts[phase_name]["items_succeeded"] += 1

        if phase_name.lower() in ['interpretation', 'categorization', 'generation']:
            self.record_llm_duration(phase_name.lower(), duration)

    def get_counter(self, name: str, default=0) -> int:
        if name == "items_processed_overall_distinct":
            return len(self.items_processed_overall_distinct)
        return self.counters.get(name, default)

    def get_report(self) -> str:
        """Generates a summary report of the processing run."""
        report_lines = ["--- Processing Stats Report ---"]
        total_duration = (self.end_time - self.start_time) if self.end_time and self.start_time else \
                         (time.monotonic() - self.start_time) if self.start_time else 0.0
        report_lines.append(f"Total Run Time: {total_duration:.2f} seconds")

        report_lines.append("\nPhase Summary:")
        for phase, counts in sorted(self.phase_counts.items()):
            report_lines.append(
                f"  - {phase.capitalize()}: "
                f"Orchestration (Entries={counts['orchestration_entries']}, Comp={counts['orchestration_completions']}, Fail={counts['orchestration_failures']}), "
                f"Items (Attempted={counts['items_attempted']}, Success={counts['items_succeeded']}, Fail={counts['items_failed']})"
            )

        report_lines.append("\nAverage LLM Durations (last 20):")
        for phase in ['interpret', 'categorize', 'generate']:
             avg_duration = self.get_avg_llm_duration(phase)
             count = len(self.llm_durations[phase])
             if avg_duration is not None:
                 report_lines.append(f"  - {phase.capitalize()}: {avg_duration:.2f}s (based on {count} samples)")
             else:
                  report_lines.append(f"  - {phase.capitalize()}: No data")

        report_lines.append(f"  Overall Items Processed (Distinct): {self.get_counter('items_processed_overall_distinct')} / {self.total_items_in_run}")

        if self.errors:
            report_lines.append(f"\nErrors Recorded ({len(self.errors)} total - showing up to 10):")
            for i, (phase, tweet_id, msg, _exception_obj) in enumerate(self.errors[:10]):
                item_context = f" (Item: {tweet_id})" if tweet_id else ""
                report_lines.append(f"  {i+1}. [{phase.capitalize()}]{item_context} {msg}")
            if len(self.errors) > 10:
                report_lines.append("  ... (more errors logged)")

        report_lines.append("--- End Report ---")
        return "\n".join(report_lines)
