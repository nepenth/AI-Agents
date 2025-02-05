import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from knowledge_base_agent.image_interpreter import interpret_image

class TestImageInterpreter(unittest.TestCase):
    @patch("knowledge_base_agent.image_interpreter.requests.post")
    def test_interpret_image_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test description"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        temp_image = Path("temp_test.jpg")
        temp_image.write_bytes(b"fake image data")
        description = interpret_image("http://localhost", temp_image, "vision_model")
        self.assertEqual(description, "Test description")
        temp_image.unlink()

if __name__ == '__main__':
    unittest.main()
