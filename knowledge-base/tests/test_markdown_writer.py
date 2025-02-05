import unittest
from pathlib import Path
import shutil
import tempfile
from knowledge_base_agent.markdown_writer import write_tweet_markdown, generate_root_readme, clean_text_for_categorization
from knowledge_base_agent.category_manager import CategoryManager

class TestMarkdownWriter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.category_manager = CategoryManager(self.temp_dir / "categories.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_clean_text_for_categorization(self):
        text = "Hello\nWorld\n"
        cleaned = clean_text_for_categorization(text)
        self.assertNotIn("\n", cleaned)

    def test_write_tweet_markdown(self):
        tweet_id = "123456"
        main_category = "software_engineering"
        sub_category = "best_practices"
        item_name = "kubernetes_pod_networking"
        tweet_text = "Test tweet text"
        image_files = []
        image_descriptions = ["Test image description"]
        tweet_url = "http://twitter.com/test"
        write_tweet_markdown(
            root_dir=self.temp_dir,
            tweet_id=tweet_id,
            main_category=main_category,
            sub_category=sub_category,
            item_name=item_name,
            tweet_text=tweet_text,
            image_files=image_files,
            image_descriptions=image_descriptions,
            tweet_url=tweet_url
        )
        item_path = self.temp_dir / main_category / sub_category / item_name
        self.assertTrue(item_path.exists())
        content_md = item_path / "content.md"
        self.assertTrue(content_md.exists())

    def test_generate_root_readme(self):
        main_cat_dir = self.temp_dir / "software_engineering"
        sub_cat_dir = main_cat_dir / "best_practices"
        sub_cat_dir.mkdir(parents=True, exist_ok=True)
        item_dir = sub_cat_dir / "dummy_item"
        item_dir.mkdir()
        content_md = item_dir / "content.md"
        content_md.write_text("# Dummy Item\n**Tweet Text:** Dummy tweet")
        generate_root_readme(self.temp_dir, self.category_manager)
        readme_path = self.temp_dir / "README.md"
        self.assertTrue(readme_path.exists())

if __name__ == '__main__':
    unittest.main()
