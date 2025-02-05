import unittest
import tempfile
import os
import shutil
from pathlib import Path
from knowledge_base_agent.cleanup import clean_untitled_directories, delete_knowledge_base_item

class TestCleanup(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.untitled_dir = self.temp_dir / "software_engineering" / "best_practices" / "untitled_test"
        self.untitled_dir.mkdir(parents=True, exist_ok=True)
        self.processed_tweets = {"123": {"item_name": "untitled_test", "main_category": "software_engineering", "sub_category": "best_practices"}}

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_clean_untitled_directories(self):
        clean_untitled_directories(self.temp_dir)
        self.assertFalse(self.untitled_dir.exists())

    def test_delete_knowledge_base_item(self):
        self.untitled_dir.mkdir(parents=True, exist_ok=True)
        delete_knowledge_base_item("123", self.processed_tweets, self.temp_dir)
        self.assertFalse(self.untitled_dir.exists())

if __name__ == '__main__':
    unittest.main()
