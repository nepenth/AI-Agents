"""
Statistics Manager for the Knowledge Base Agent.

Handles loading and saving of processing statistics, such as average time per item
for different processing phases, to aid in ETC (Estimated Time to Completion) calculations.
"""
from pathlib import Path
import json
import logging
import os
from typing import Dict, Any
from datetime import datetime, timezone

STATS_FILE_PATH = Path("data/processing_stats.json")

def load_processing_stats(stats_file: Path = STATS_FILE_PATH) -> Dict[str, Any]:
    """Loads processing statistics from the JSON file."""
    default_stats = {"phases": {}, "last_updated_timestamp": None}
    if not stats_file.exists():
        logging.info(f"Processing stats file not found at {stats_file}. Returning default stats.")
        return default_stats
    try:
        with open(stats_file, "r", encoding='utf-8') as f:
            data = json.load(f)
            if "phases" not in data: # Ensure basic structure
                data["phases"] = {}
            logging.info(f"Successfully loaded processing stats from {stats_file}")
            return data
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error loading processing stats from {stats_file}: {e}. Returning default stats.")
        return default_stats

def save_processing_stats(data: Dict[str, Any], stats_file: Path = STATS_FILE_PATH) -> None:
    """Saves processing statistics to the JSON file atomically."""
    try:
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file_path = stats_file.with_suffix(stats_file.suffix + ".tmp")
        with open(temp_file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file_path, stats_file) # Atomic rename
        logging.info(f"Successfully saved processing stats to {stats_file}")
    except IOError as e:
        logging.error(f"Error saving processing stats to {stats_file}: {e}")

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