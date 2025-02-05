import unittest
from unittest.mock import patch
import tempfile
import shutil
from pathlib import Path
from knowledge_base_agent.reprocess import reprocess_existing_items
from knowledge_base_agent.category_manager import CategoryManager

class TestReprocess(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.main_cat_dir = self.temp_dir / "software_engineering"
        self.sub_cat_dir = self.main_cat_dir / "best_practices"
        self.item_dir = self.sub_cat_dir / "dummy_item"
        self.item_dir.mkdir(parents=True, exist_ok=True)
        self.content_file = self.item_dir / "content.md"
        self.content_file.write_text("# dummy_item\nDummy content")
        self.category_manager = CategoryManager(self.temp_dir / "dummy_categories.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch("builtins.input", side_effect=["y", "y"])
    def test_reprocess_existing_items(self, mock_input):
        reprocess_existing_items(self.temp_dir, self.category_manager)
        self.assertFalse(self.item_dir.exists())

if __name__ == '__main__':
    unittest.main()
