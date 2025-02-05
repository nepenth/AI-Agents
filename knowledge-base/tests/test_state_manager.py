import unittest
import tempfile
import os
import json
from pathlib import Path
from knowledge_base_agent.state_manager import load_processed_tweets, save_processed_tweets

class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.file_path = Path(self.temp_file.name)
        self.test_data = {"123": {"item_name": "test_item", "main_category": "software_engineering", "sub_category": "best_practices"}}
        save_processed_tweets(self.file_path, self.test_data)

    def tearDown(self):
        os.unlink(self.temp_file.name)

    def test_load_processed_tweets(self):
        data = load_processed_tweets(self.file_path)
        self.assertEqual(data, self.test_data)

if __name__ == '__main__':
    unittest.main()
