import sqlite3
import os
import csv
from datetime import datetime
import logging
import re # Import regex

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataManager:
    """Handles storage and retrieval of analysis results in SQLite."""

    def __init__(self, db_path="data/database.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database and create the results table if it doesn't exist."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Add columns for structured card details
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_path TEXT NOT NULL,       -- Original image path
                        item_type TEXT NOT NULL,
                        description TEXT,               -- Raw OCR text from cropped
                        insights TEXT,                  -- Full structured insights string from LLM
                        ebay_value TEXT,
                        vivino_value TEXT,              -- Keep for wine
                        drink_window TEXT,              -- Keep for wine
                        ebay_search_url TEXT,
                        cropped_image_path TEXT,        -- Path to cropped image
                        card_player TEXT,               -- Extracted Player Name
                        card_year TEXT,                 -- Extracted Year
                        card_brand TEXT,                -- Extracted Brand/Set
                        card_value_insight TEXT,        -- Extracted Value from insights LLM
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Add columns if they don't exist
                cursor.execute("PRAGMA table_info(results)")
                columns = [col[1] for col in cursor.fetchall()]
                # Add new columns to check list
                new_cols = ['ebay_value', 'vivino_value', 'drink_window', 'ebay_search_url', 
                            'cropped_image_path', 'card_player', 'card_year', 'card_brand', 
                            'card_value_insight']
                for col in new_cols: 
                    if col not in columns:
                        cursor.execute(f"ALTER TABLE results ADD COLUMN {col} TEXT")
                        logger.info(f"Added column '{col}' to results table.")
                conn.commit()
                logger.info(f"Initialized database at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise ValueError(f"Failed to initialize database: {str(e)}")

    def save_result(self, image_path, item_type, description, insights, 
                    ebay_value=None, vivino_value=None, drink_window=None, ebay_search_url=None, 
                    cropped_image_path=None, card_player=None, card_year=None, card_brand=None, 
                    card_value_insight=None):
        """Save an analysis result, including structured fields, to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Add new fields to INSERT statement (13 placeholders)
                sql = """
                    INSERT INTO results (
                        image_path, item_type, description, insights, ebay_value, 
                        vivino_value, drink_window, ebay_search_url, cropped_image_path, 
                        card_player, card_year, card_brand, card_value_insight
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                """
                params = (
                    image_path, item_type, description, insights, ebay_value, 
                    vivino_value, drink_window, ebay_search_url, cropped_image_path, 
                    card_player, card_year, card_brand, card_value_insight
                )
                cursor.execute(sql, params)
                conn.commit()
                logger.info(f"Saved result for item associated with {image_path}")
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving result: {str(e)}")
            raise ValueError(f"Failed to save result: {str(e)}")

    def update_result_details(self, result_id, player, year, brand):
        """Update the editable details for a specific result ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                sql = """
                    UPDATE results 
                    SET card_player = ?, card_year = ?, card_brand = ?
                    WHERE id = ?
                """
                cursor.execute(sql, (player, year, brand, result_id))
                conn.commit()
                logger.info(f"Updated details for result ID {result_id}")
                return cursor.rowcount > 0 # Return True if update was successful
        except sqlite3.Error as e:
            logger.error(f"Error updating result {result_id}: {str(e)}")
            return False

    def get_all_results(self):
        """Retrieve all results from the database as dictionaries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row 
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM results ORDER BY timestamp DESC")
                results = cursor.fetchall()
                return [dict(row) for row in results] 
        except sqlite3.Error as e:
            logger.error(f"Error retrieving results: {str(e)}")
            raise ValueError(f"Failed to retrieve results: {str(e)}")

    def get_result_by_id(self, result_id):
        """Retrieve a single result by ID as a dictionary."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM results WHERE id = ?", (result_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving result {result_id}: {str(e)}")
            raise ValueError(f"Failed to retrieve result: {str(e)}")

    def export_to_csv(self, output_path="data/exports/results.csv", item_type=None):
        """Export results to a CSV file, optionally filtered by item_type."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            results = self.get_all_results()
            if item_type:
                results = [r for r in results if r["item_type"].lower() == item_type.lower()]
            
            if not results:
                logger.info(f"No {item_type or 'results'} to export")
                return False

            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                if item_type and item_type.lower() == "wine bottle":
                    # Custom fields for wine bottle stickers
                    fieldnames = ['description', 'insights', 'vivino_value', 'drink_window']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for result in results:
                        writer.writerow({
                            'description': result['description'],
                            'insights': result['insights'],
                            'vivino_value': result['vivino_value'],
                            'drink_window': result['drink_window']
                        })
                else:
                    # Full export for all results
                    fieldnames = ['id', 'image_path', 'item_type', 'description', 'insights', 'ebay_value', 'vivino_value', 'drink_window', 'ebay_search_url', 'timestamp']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for result in results:
                        writer.writerow(result)
            logger.info(f"Exported {item_type or 'all'} results to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting to CSV: {str(e)}")
            raise ValueError(f"Failed to export to CSV: {str(e)}")

    def delete_result_by_id(self, result_id):
        """Delete a single result by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
                conn.commit()
                logger.info(f"Deleted result with ID {result_id}")
                return cursor.rowcount > 0 # Return True if a row was deleted
        except sqlite3.Error as e:
            logger.error(f"Error deleting result {result_id}: {str(e)}")
            # Consider raising an error or returning False
            return False

    def delete_all_results(self):
        """Delete all results from the table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM results")
                # Optional: Reset autoincrement counter if desired
                # cursor.execute("DELETE FROM sqlite_sequence WHERE name='results'") 
                conn.commit()
                logger.info("Deleted all results from the database")
                return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting all results: {str(e)}")
            return False

    # --- Add Method to Update eBay Info ---
    def update_result_ebay_info(self, result_id, ebay_value, ebay_search_url):
        """Update the eBay value and URL for a specific result ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                sql = """
                    UPDATE results 
                    SET ebay_value = ?, ebay_search_url = ?
                    WHERE id = ?
                """
                cursor.execute(sql, (ebay_value, ebay_search_url, result_id))
                conn.commit()
                logger.info(f"Updated eBay info for result ID {result_id}")
                return cursor.rowcount > 0 # Return True if update was successful
        except sqlite3.Error as e:
            logger.error(f"Error updating eBay info for result {result_id}: {str(e)}")
            return False