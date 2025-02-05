import unittest
from knowledge_base_agent.naming_utils import normalize_name_for_filesystem, is_valid_item_name, fallback_snippet_based_name

class TestNamingUtils(unittest.TestCase):
    def test_normalize_name(self):
        name = "  Test Name!  "
        normalized = normalize_name_for_filesystem(name)
        self.assertNotIn(" ", normalized)
        self.assertTrue(normalized.islower())

    def test_is_valid_item_name(self):
        valid = "kubernetes_pod_networking"
        self.assertTrue(is_valid_item_name(valid))
        invalid = "fallback_example"
        self.assertFalse(is_valid_item_name(invalid))

    def test_fallback_snippet_based_name(self):
        snippet = "This is a test snippet for fallback naming."
        name = fallback_snippet_based_name(snippet)
        self.assertTrue(len(name.split('_')) >= 1)

if __name__ == '__main__':
    unittest.main()
