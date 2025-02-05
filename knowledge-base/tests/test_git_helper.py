import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from knowledge_base_agent.git_helper import run_git_command

class TestGitHelper(unittest.TestCase):
    @patch("knowledge_base_agent.git_helper.subprocess.run")
    def test_run_git_command_success(self, mock_run):
        mock_process = MagicMock()
        mock_process.stdout = "output"
        mock_run.return_value = mock_process
        output = run_git_command(["git", "--version"], cwd=Path("."), capture_output=True)
        self.assertEqual(output, "output")

    @patch("knowledge_base_agent.git_helper.subprocess.run", side_effect=Exception("fail"))
    def test_run_git_command_failure(self, mock_run):
        output = run_git_command(["git", "invalid"], cwd=Path("."), capture_output=True)
        self.assertIsNone(output)

if __name__ == '__main__':
    unittest.main()
