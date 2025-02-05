import unittest
from unittest.mock import patch, MagicMock
import asyncio
from knowledge_base_agent.ai_categorization import process_category_response, categorize_and_name_content
from knowledge_base_agent.category_manager import CategoryManager
from pathlib import Path

class TestAICategorization(unittest.TestCase):
    def test_process_category_response_valid(self):
        response = "Software Engineering | Best Practices | Kubernetes Pod Networking"
        main_cat, sub_cat, item_name = process_category_response(response, "123456")
        self.assertEqual(main_cat, "software_engineering")
        self.assertEqual(sub_cat, "best_practices")
        self.assertEqual(item_name, "kubernetes_pod_networking")

    @patch("knowledge_base_agent.ai_categorization.requests.post")
    def test_categorize_and_name_content(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Software Engineering | Best Practices | Kubernetes Pod Networking"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        category_manager = CategoryManager(Path("dummy.json"))
        async def run_test():
            result = await categorize_and_name_content("http://localhost", "Test tweet content", "test_model", "123456", category_manager)
            self.assertEqual(result[0], "software_engineering")
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
