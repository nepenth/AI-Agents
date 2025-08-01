"""
Statistics Manager for the Knowledge Base Agent.

Handles loading and saving of processing statistics, such as average time per item
for different processing phases, to aid in ETC (Estimated Time to Completion) calculations.
Enhanced with dynamic real-time phase estimation based on item processing averages.

MIGRATED: Now uses ProcessingStatistics database model instead of JSON files.
"""
from pathlib import Path
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from collections import deque
import statistics

# Legacy file path for fallback compatibility
STATS_FILE_PATH = Path("data/processing_stats.json")

def load_processing_stats(stats_file: Path = STATS_FILE_PATH) -> Dict[str, Any]:
    """
    Loads processing statistics from database.
    
    MIGRATED: Now uses ProcessingStatistics database model exclusively.
    """
    default_stats = {
        "phases": {},
        "last_updated_timestamp": None,
        "runtime_phase_estimates": {}  # New: stores dynamic estimates during runs
    }
    
    # Load from database
    try:
        from flask import current_app
        from .models import ProcessingStatistics
        
        if not current_app:
            logging.error("No Flask app context available for loading processing stats")
            return default_stats
            
        with current_app.app_context():
            db_stats = ProcessingStatistics.query.all()
            if not db_stats:
                logging.info("No processing statistics found in database")
                return default_stats
                
            phases = {}
            last_updated = None
            
            for stat in db_stats:
                if stat.metric_name == 'historical_average':
                    phases[stat.phase_name] = {
                        "total_items_processed": stat.total_items_processed,
                        "total_duration_seconds": float(stat.total_duration_seconds) if stat.total_duration_seconds else 0.0,
                        "avg_time_per_item_seconds": float(stat.avg_time_per_item_seconds) if stat.avg_time_per_item_seconds else 0.0
                    }
                    if not last_updated or (stat.recorded_at and stat.recorded_at > last_updated):
                        last_updated = stat.recorded_at
            
            logging.debug(f"Successfully loaded processing stats from database: {len(phases)} phases")
            return {
                "phases": phases,
                "last_updated_timestamp": last_updated.isoformat() if last_updated else None,
                "runtime_phase_estimates": {}
            }
            
    except Exception as e:
        logging.error(f"Failed to load processing stats from database: {e}")
        return default_stats

def save_processing_stats(data: Dict[str, Any], stats_file: Path = STATS_FILE_PATH) -> None:
    """
    Saves processing statistics to database.
    
    MIGRATED: Now uses ProcessingStatistics database model exclusively.
    """
    try:
        from flask import current_app
        from .models import ProcessingStatistics, db
        
        if not current_app:
            logging.error("No Flask app context available for saving processing stats")
            return
            
        with current_app.app_context():
            phases_data = data.get("phases", {})
            
            for phase_id, phase_stats in phases_data.items():
                # Check if record exists
                existing_stat = ProcessingStatistics.query.filter_by(
                    phase_name=phase_id, 
                    metric_name='historical_average'
                ).first()
                
                if existing_stat:
                    # Update existing record
                    existing_stat.total_items_processed = phase_stats.get('total_items_processed', 0)
                    existing_stat.total_duration_seconds = phase_stats.get('total_duration_seconds', 0.0)
                    existing_stat.avg_time_per_item_seconds = phase_stats.get('avg_time_per_item_seconds', 0.0)
                    existing_stat.metric_value = phase_stats.get('avg_time_per_item_seconds', 0.0)
                    existing_stat.recorded_at = datetime.now(timezone.utc)
                else:
                    # Create new record
                    new_stat = ProcessingStatistics(
                        phase_name=phase_id,
                        metric_name='historical_average',
                        metric_value=phase_stats.get('avg_time_per_item_seconds', 0.0),
                        metric_unit='seconds_per_item',
                        total_items_processed=phase_stats.get('total_items_processed', 0),
                        total_duration_seconds=phase_stats.get('total_duration_seconds', 0.0),
                        avg_time_per_item_seconds=phase_stats.get('avg_time_per_item_seconds', 0.0),
                        run_id='historical_data',
                        recorded_at=datetime.now(timezone.utc)
                    )
                    db.session.add(new_stat)
            
            db.session.commit()
            logging.debug(f"Successfully saved processing stats to database: {len(phases_data)} phases")
            
    except Exception as e:
        logging.error(f"Failed to save processing stats to database: {e}")
        raise

def update_phase_stats(
    phase_id: str,
    items_processed_this_run: int,
    duration_this_run_seconds: float,
    stats_file: Path = STATS_FILE_PATH
) -> Dict[str, Any]:
    """
    Loads, updates, and saves statistics for a given processing phase.

    Args:
        phase_id: Identifier for the phase (e.g., "llm_categorization").
        items_processed_this_run: Number of items successfully processed in the current run for this phase.
        duration_this_run_seconds: Total duration of processing for this phase in the current run.
        stats_file: Path to the statistics file.

    Returns:
        The updated historical statistics for the phase.
    """
    if items_processed_this_run <= 0:
        logging.info(f"No items processed for phase '{phase_id}' in this run. Stats not updated.")
        # Still load and return current stats if needed by caller
        current_stats_data = load_processing_stats(stats_file)
        return current_stats_data.get("phases", {}).get(phase_id, {
            "total_items_processed": 0,
            "total_duration_seconds": 0.0,
            "avg_time_per_item_seconds": 0.0
        })

    processing_stats_data = load_processing_stats(stats_file) # Load current stats

    phase_historical_stats = processing_stats_data.setdefault("phases", {}).setdefault(phase_id, {
        "total_items_processed": 0,
        "total_duration_seconds": 0.0,
        "avg_time_per_item_seconds": 0.0
    })

    phase_historical_stats["total_items_processed"] += items_processed_this_run
    phase_historical_stats["total_duration_seconds"] += duration_this_run_seconds

    if phase_historical_stats["total_items_processed"] > 0:
        phase_historical_stats["avg_time_per_item_seconds"] = \
            phase_historical_stats["total_duration_seconds"] / phase_historical_stats["total_items_processed"]
    else:
        phase_historical_stats["avg_time_per_item_seconds"] = 0.0 # Avoid division by zero

    processing_stats_data["last_updated_timestamp"] = datetime.now(timezone.utc).isoformat()
    save_processing_stats(processing_stats_data, stats_file) # Save updated stats

    logging.info(f"Updated historical stats for phase '{phase_id}': Added {items_processed_this_run} items, {duration_this_run_seconds:.2f}s. New avg: {phase_historical_stats['avg_time_per_item_seconds']:.2f}s/item.")
    return phase_historical_stats 

class DynamicPhaseEstimator:
    """
    Manages dynamic phase completion estimation based on real-time item processing times.
    """
    
    def __init__(self, stats_file: Path = STATS_FILE_PATH):
        self.stats_file = stats_file
        self.runtime_estimates: Dict[str, Dict[str, Any]] = {}
        self._load_historical_data()
    
    def _load_historical_data(self):
        """Load historical average times for initial estimates."""
        stats_data = load_processing_stats(self.stats_file)
        self.historical_phases = stats_data.get("phases", {})
        logging.debug(f"Loaded historical data for {len(self.historical_phases)} phases")
    
    def initialize_phase_tracking(self, phase_id: str, total_items: int) -> Optional[float]:
        """
        Initialize tracking for a new phase and return initial ETC based on historical data.
        
        Args:
            phase_id: Phase identifier
            total_items: Total number of items to process in this phase
            
        Returns:
            Estimated duration in seconds based on historical data, or None if no historical data
        """
        # Initialize runtime tracking for this phase
        self.runtime_estimates[phase_id] = {
            "total_items": total_items,
            "processed_items": 0,
            "start_time": datetime.now(timezone.utc).timestamp(),
            "item_processing_times": deque(maxlen=50),  # Keep last 50 item times for rolling average
            "current_avg_time_per_item": 0.0,
            "estimated_completion_timestamp": None,
            "last_update_time": datetime.now(timezone.utc).timestamp()
        }
        
        # Get historical average if available
        historical_data = self.historical_phases.get(phase_id, {})
        historical_avg = historical_data.get("avg_time_per_item_seconds", 0.0)
        
        if historical_avg > 0:
            estimated_duration = historical_avg * total_items
            estimated_completion = datetime.now(timezone.utc).timestamp() + estimated_duration
            self.runtime_estimates[phase_id]["estimated_completion_timestamp"] = estimated_completion
            logging.info(f"Phase '{phase_id}': Initial ETC based on historical avg {historical_avg:.2f}s/item = {estimated_duration:.0f}s total")
            return estimated_duration
        
        logging.info(f"Phase '{phase_id}': No historical data available for initial ETC")
        return None
    
    def update_phase_progress(self, phase_id: str, processed_items: int, current_item_duration: Optional[float] = None) -> Dict[str, Any]:
        """
        Update progress for a phase and recalculate dynamic ETC.
        
        Args:
            phase_id: Phase identifier
            processed_items: Number of items completed so far
            current_item_duration: Time taken to process the most recent item(s)
            
        Returns:
            Dictionary with updated estimates including ETC timestamp
        """
        if phase_id not in self.runtime_estimates:
            logging.debug(f"Phase '{phase_id}' not initialized for tracking (likely completed with 0 items)")
            return {}
        
        phase_data = self.runtime_estimates[phase_id]
        current_time = datetime.now(timezone.utc).timestamp()
        
        # Update processed count
        previous_processed = phase_data["processed_items"]
        phase_data["processed_items"] = processed_items
        phase_data["last_update_time"] = current_time
        
        # Calculate time per item if we have duration data
        if current_item_duration is not None and current_item_duration > 0:
            phase_data["item_processing_times"].append(current_item_duration)
        elif processed_items > previous_processed:
            # Calculate elapsed time since last update for batch processing
            elapsed_since_last = current_time - phase_data["last_update_time"]
            items_processed_since_last = processed_items - previous_processed
            if items_processed_since_last > 0 and elapsed_since_last > 0:
                avg_time_per_item_in_batch = elapsed_since_last / items_processed_since_last
                # Only add reasonable times (filter out very fast or very slow outliers)
                if 0.1 <= avg_time_per_item_in_batch <= 3600:  # Between 0.1s and 1 hour per item
                    phase_data["item_processing_times"].append(avg_time_per_item_in_batch)
        
        # Calculate current average time per item using recent data
        if phase_data["item_processing_times"]:
            # Use median of recent times to reduce impact of outliers
            recent_times = list(phase_data["item_processing_times"])
            phase_data["current_avg_time_per_item"] = statistics.median(recent_times)
        else:
            # Fall back to historical average
            historical_data = self.historical_phases.get(phase_id, {})
            phase_data["current_avg_time_per_item"] = historical_data.get("avg_time_per_item_seconds", 0.0)
        
        # Calculate new ETC
        remaining_items = phase_data["total_items"] - processed_items
        if remaining_items > 0 and phase_data["current_avg_time_per_item"] > 0:
            estimated_remaining_seconds = remaining_items * phase_data["current_avg_time_per_item"]
            phase_data["estimated_completion_timestamp"] = current_time + estimated_remaining_seconds
        else:
            phase_data["estimated_completion_timestamp"] = current_time  # Done or nearly done
        
        # Log progress update
        if processed_items > previous_processed:
            progress_pct = (processed_items / phase_data["total_items"]) * 100 if phase_data["total_items"] > 0 else 0
            etc_minutes = (phase_data["estimated_completion_timestamp"] - current_time) / 60 if phase_data["estimated_completion_timestamp"] else 0
            logging.info(f"Phase '{phase_id}': {processed_items}/{phase_data['total_items']} ({progress_pct:.1f}%) - ETC: {etc_minutes:.1f}min (avg: {phase_data['current_avg_time_per_item']:.1f}s/item)")
        
        return {
            "phase_id": phase_id,
            "processed_items": processed_items,
            "total_items": phase_data["total_items"],
            "current_avg_time_per_item": phase_data["current_avg_time_per_item"],
            "estimated_completion_timestamp": phase_data["estimated_completion_timestamp"],
            "estimated_remaining_minutes": (phase_data["estimated_completion_timestamp"] - current_time) / 60 if phase_data["estimated_completion_timestamp"] else 0
        }
    
    def get_phase_estimate(self, phase_id: str) -> Optional[Dict[str, Any]]:
        """Get current estimate data for a phase."""
        if phase_id not in self.runtime_estimates:
            return None
        
        phase_data = self.runtime_estimates[phase_id]
        current_time = datetime.now(timezone.utc).timestamp()
        
        return {
            "phase_id": phase_id,
            "processed_items": phase_data["processed_items"],
            "total_items": phase_data["total_items"],
            "current_avg_time_per_item": phase_data["current_avg_time_per_item"],
            "estimated_completion_timestamp": phase_data["estimated_completion_timestamp"],
            "estimated_remaining_minutes": (phase_data["estimated_completion_timestamp"] - current_time) / 60 if phase_data["estimated_completion_timestamp"] else 0
        }
    
    def finalize_phase(self, phase_id: str) -> None:
        """
        Clean up tracking data when a phase completes and update historical stats.
        """
        if phase_id not in self.runtime_estimates:
            return
        
        phase_data = self.runtime_estimates[phase_id]
        
        # Calculate final stats for this run
        total_duration = datetime.now(timezone.utc).timestamp() - phase_data["start_time"]
        items_processed = phase_data["processed_items"]
        
        if items_processed > 0:
            # Update historical stats with this run's data
            update_phase_stats(phase_id, items_processed, total_duration, self.stats_file)
            logging.info(f"Phase '{phase_id}' completed: {items_processed} items in {total_duration:.1f}s")
        
        # Clean up runtime data
        del self.runtime_estimates[phase_id]
    
    def get_all_active_estimates(self) -> Dict[str, Dict[str, Any]]:
        """Get estimates for all currently active phases."""
        current_time = datetime.now(timezone.utc).timestamp()
        estimates = {}
        
        for phase_id, phase_data in self.runtime_estimates.items():
            estimates[phase_id] = {
                "processed_items": phase_data["processed_items"],
                "total_items": phase_data["total_items"],
                "current_avg_time_per_item": phase_data["current_avg_time_per_item"],
                "estimated_completion_timestamp": phase_data["estimated_completion_timestamp"],
                "estimated_remaining_minutes": (phase_data["estimated_completion_timestamp"] - current_time) / 60 if phase_data["estimated_completion_timestamp"] else 0
            }
        
        return estimates

def get_historical_phase_average(phase_id: str, stats_file: Path = STATS_FILE_PATH) -> float:
    """
    Get the historical average time per item for a specific phase.
    
    Args:
        phase_id: Phase identifier
        stats_file: Path to stats file
        
    Returns:
        Average time per item in seconds, or 0.0 if no historical data
    """
    stats_data = load_processing_stats(stats_file)
    phase_data = stats_data.get("phases", {}).get(phase_id, {})
    return phase_data.get("avg_time_per_item_seconds", 0.0)

def format_duration_to_hhmm(seconds: float) -> str:
    """
    Format duration in seconds to HH:MM format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string in HH:MM format
    """
    if seconds <= 0:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}" 