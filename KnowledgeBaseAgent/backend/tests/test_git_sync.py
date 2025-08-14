"""Tests for Git sync functionality."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.git_sync_service import (
    GitSyncService, GitConfig, GitOperations, FileExporter, GitSyncResult
)


@pytest.fixture
def git_config():
    """Create test Git configuration."""
    return GitConfig(
        repo_url="https://github.com/test/repo.git",
        branch="main",
        username="testuser",
        password="testpass",
        commit_author_name="Test User",
        commit_author_email="test@example.com"
    )


@pytest.fixture
def temp_directory():
    """Create temporary directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def git_sync_service():
    """Create Git sync service for testing."""
    return GitSyncService()


class TestGitOperations:
    """Test cases for GitOperations."""
    
    def test_git_operations_init(self, git_config, temp_directory):
        """Test GitOperations initialization."""
        git_ops = GitOperations(temp_directory, git_config)
        
        assert git_ops.repo_path == temp_directory
        assert git_ops.config == git_config
    
    @pytest.mark.asyncio
    async def test_clone_or_pull_new_repo(self, git_config, temp_directory):
        """Test cloning a new repository."""
        git_ops = GitOperations(temp_directory, git_config)
        
        with patch.object(git_ops, '_run_git_command') as mock_git:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_git.return_value = mock_process
            
            result = await git_ops.clone_or_pull()
            
            assert result is True
            mock_git.assert_called_once()
            args = mock_git.call_args[0][0]
            assert args[0] == "clone"
            assert git_config.repo_url in args
    
    @pytest.mark.asyncio
    async def test_clone_or_pull_existing_repo(self, git_config, temp_directory):
        """Test pulling from existing repository."""
        # Create .git directory to simulate existing repo
        git_dir = temp_directory / ".git"
        git_dir.mkdir()
        
        git_ops = GitOperations(temp_directory, git_config)
        
        with patch.object(git_ops, '_run_git_command') as mock_git:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_git.return_value = mock_process
            
            result = await git_ops.clone_or_pull()
            
            assert result is True
            mock_git.assert_called_once()
            args = mock_git.call_args[0][0]
            assert args[0] == "pull"
    
    @pytest.mark.asyncio
    async def test_add_and_commit_with_changes(self, git_config, temp_directory):
        """Test adding and committing changes."""
        git_ops = GitOperations(temp_directory, git_config)
        
        with patch.object(git_ops, '_run_git_command') as mock_git:
            # Mock git status to show changes
            status_process = Mock()
            status_process.returncode = 0
            status_process.stdout = "M file.txt\n"
            
            # Mock git commit to return success
            commit_process = Mock()
            commit_process.returncode = 0
            
            # Mock git rev-parse to return commit hash
            hash_process = Mock()
            hash_process.returncode = 0
            hash_process.stdout = "abc123def456"
            
            mock_git.side_effect = [
                Mock(returncode=0),  # git add
                status_process,      # git status
                Mock(returncode=0),  # git config user.name
                Mock(returncode=0),  # git config user.email
                commit_process,      # git commit
                hash_process         # git rev-parse
            ]
            
            commit_hash = await git_ops.add_and_commit("Test commit")
            
            assert commit_hash == "abc123def456"
            assert mock_git.call_count == 6
    
    @pytest.mark.asyncio
    async def test_add_and_commit_no_changes(self, git_config, temp_directory):
        """Test commit when there are no changes."""
        git_ops = GitOperations(temp_directory, git_config)
        
        with patch.object(git_ops, '_run_git_command') as mock_git:
            # Mock git status to show no changes
            status_process = Mock()
            status_process.returncode = 0
            status_process.stdout = ""
            
            mock_git.side_effect = [
                Mock(returncode=0),  # git add
                status_process       # git status
            ]
            
            commit_hash = await git_ops.add_and_commit("Test commit")
            
            assert commit_hash is None
            assert mock_git.call_count == 2
    
    @pytest.mark.asyncio
    async def test_push_success(self, git_config, temp_directory):
        """Test successful push operation."""
        git_ops = GitOperations(temp_directory, git_config)
        
        with patch.object(git_ops, '_run_git_command') as mock_git:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_git.return_value = mock_process
            
            result = await git_ops.push()
            
            assert result is True
            mock_git.assert_called_once()
            args = mock_git.call_args[0][0]
            assert args[0] == "push"
    
    @pytest.mark.asyncio
    async def test_get_changed_files(self, git_config, temp_directory):
        """Test getting list of changed files."""
        git_ops = GitOperations(temp_directory, git_config)
        
        with patch.object(git_ops, '_run_git_command') as mock_git:
            mock_process = Mock()
            mock_process.returncode = 0
            mock_process.stdout = "file1.txt\nfile2.md\ndir/file3.json\n"
            mock_git.return_value = mock_process
            
            changed_files = await git_ops.get_changed_files()
            
            assert len(changed_files) == 3
            assert "file1.txt" in changed_files
            assert "file2.md" in changed_files
            assert "dir/file3.json" in changed_files


class TestFileExporter:
    """Test cases for FileExporter."""
    
    def test_file_exporter_init(self, temp_directory):
        """Test FileExporter initialization."""
        exporter = FileExporter(temp_directory)
        
        assert exporter.export_dir == temp_directory
        assert exporter.exported_files == []
    
    @pytest.mark.asyncio
    async def test_export_all_content(self, temp_directory):
        """Test exporting all content from database."""
        exporter = FileExporter(temp_directory)
        
        # Mock database repositories
        with patch('app.services.git_sync_service.get_db_session'):
            with patch('app.services.git_sync_service.get_content_repository') as mock_content_repo:
                with patch('app.services.git_sync_service.get_knowledge_repository') as mock_knowledge_repo:
                    with patch('app.services.git_sync_service.get_synthesis_repository') as mock_synthesis_repo:
                        with patch('app.services.git_sync_service.get_readme_repository') as mock_readme_repo:
                            # Mock repository responses
                            mock_content_repo.return_value.list.return_value = [
                                Mock(
                                    id="content-1",
                                    title="Test Content",
                                    content="Test content body",
                                    main_category="test",
                                    sub_category=None,
                                    source_type="manual",
                                    source_url=None,
                                    tags=["test"],
                                    created_at=datetime.utcnow()
                                )
                            ]
                            
                            mock_knowledge_repo.return_value.list.return_value = []
                            mock_synthesis_repo.return_value.list.return_value = []
                            mock_readme_repo.return_value.list.return_value = []
                            
                            stats = await exporter.export_all_content()
                            
                            assert stats['content_items'] == 1
                            assert stats['knowledge_items'] == 0
                            assert stats['synthesis_documents'] == 0
                            assert stats['readme_files'] == 0
                            
                            # Check that file was created
                            content_dir = temp_directory / "content" / "test"
                            assert content_dir.exists()
                            
                            # Check that markdown file exists
                            md_files = list(content_dir.glob("*.md"))
                            assert len(md_files) == 1
    
    def test_sanitize_filename(self, temp_directory):
        """Test filename sanitization."""
        exporter = FileExporter(temp_directory)
        
        # Test invalid characters
        result = exporter._sanitize_filename("test<>:\"/\\|?*file")
        assert result == "test_________file"
        
        # Test long filename
        long_name = "a" * 150
        result = exporter._sanitize_filename(long_name)
        assert len(result) == 100
        
        # Test empty filename
        result = exporter._sanitize_filename("")
        assert result == "untitled"
        
        # Test filename with spaces and dots
        result = exporter._sanitize_filename("  test file.  ")
        assert result == "test file"
    
    def test_generate_content_markdown(self, temp_directory):
        """Test generating markdown for content item."""
        exporter = FileExporter(temp_directory)
        
        mock_item = Mock(
            id="test-123",
            title="Test Article",
            content="This is test content",
            source_type="manual",
            source_url="https://example.com",
            main_category="test",
            sub_category="example",
            tags=["test", "example"],
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        markdown = exporter._generate_content_markdown(mock_item)
        
        assert "# Test Article" in markdown
        assert "test-123" in markdown
        assert "This is test content" in markdown
        assert "https://example.com" in markdown
        assert "test" in markdown
        assert "example" in markdown


class TestGitSyncService:
    """Test cases for GitSyncService."""
    
    def test_git_sync_service_init(self, git_sync_service):
        """Test GitSyncService initialization."""
        assert git_sync_service.temp_dirs == []
    
    @pytest.mark.asyncio
    async def test_sync_to_repository_success(self, git_sync_service, git_config):
        """Test successful repository sync."""
        with patch('app.services.git_sync_service.Path') as mock_path:
            with patch('app.services.git_sync_service.tempfile.mkdtemp') as mock_mkdtemp:
                with patch('app.services.git_sync_service.GitOperations') as mock_git_ops:
                    with patch('app.services.git_sync_service.FileExporter') as mock_exporter:
                        # Setup mocks
                        temp_dir = Path("/tmp/test")
                        mock_mkdtemp.return_value = str(temp_dir)
                        mock_path.return_value = temp_dir
                        
                        mock_git_instance = Mock()
                        mock_git_instance.clone_or_pull.return_value = True
                        mock_git_instance.get_changed_files.return_value = ["file1.md", "file2.md"]
                        mock_git_instance.add_and_commit.return_value = "abc123"
                        mock_git_instance.push.return_value = True
                        mock_git_ops.return_value = mock_git_instance
                        
                        mock_exporter_instance = Mock()
                        mock_exporter_instance.export_all_content.return_value = {
                            'content_items': 5,
                            'knowledge_items': 3,
                            'synthesis_documents': 2,
                            'readme_files': 1
                        }
                        mock_exporter.return_value = mock_exporter_instance
                        
                        with patch.object(git_sync_service, '_record_sync_operation') as mock_record:
                            result = await git_sync_service.sync_to_repository(git_config)
                            
                            assert result.success is True
                            assert result.files_exported == 11
                            assert result.files_changed == 2
                            assert result.commit_hash == "abc123"
                            assert "Sync completed successfully" in result.message
                            
                            mock_record.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_to_repository_failure(self, git_sync_service, git_config):
        """Test repository sync failure."""
        with patch('app.services.git_sync_service.Path') as mock_path:
            with patch('app.services.git_sync_service.tempfile.mkdtemp') as mock_mkdtemp:
                with patch('app.services.git_sync_service.GitOperations') as mock_git_ops:
                    # Setup mocks to simulate failure
                    temp_dir = Path("/tmp/test")
                    mock_mkdtemp.return_value = str(temp_dir)
                    mock_path.return_value = temp_dir
                    
                    mock_git_instance = Mock()
                    mock_git_instance.clone_or_pull.return_value = False
                    mock_git_ops.return_value = mock_git_instance
                    
                    result = await git_sync_service.sync_to_repository(git_config)
                    
                    assert result.success is False
                    assert "Sync failed" in result.message
                    assert len(result.errors) > 0
    
    def test_generate_operation_id(self, git_sync_service):
        """Test operation ID generation."""
        operation_id = git_sync_service._generate_operation_id()
        
        assert operation_id.startswith("sync_")
        assert len(operation_id) > 10
    
    def test_generate_commit_message(self, git_sync_service):
        """Test commit message generation."""
        export_stats = {
            'content_items': 5,
            'knowledge_items': 3,
            'synthesis_documents': 2,
            'readme_files': 1
        }
        
        message = git_sync_service._generate_commit_message(export_stats)
        
        assert "Update knowledge base" in message
        assert "5 content items" in message
        assert "3 knowledge items" in message
        assert "2 synthesis docs" in message
        assert "1 README files" in message
        assert "Total files: 11" in message
    
    def test_generate_commit_message_empty(self, git_sync_service):
        """Test commit message generation with no changes."""
        export_stats = {
            'content_items': 0,
            'knowledge_items': 0,
            'synthesis_documents': 0,
            'readme_files': 0
        }
        
        message = git_sync_service._generate_commit_message(export_stats)
        
        assert "Update knowledge base (no changes)" in message
    
    def test_cleanup_all_temp_dirs(self, git_sync_service, temp_directory):
        """Test cleanup of all temporary directories."""
        # Add temp directory to service
        git_sync_service.temp_dirs.append(temp_directory)
        
        # Create a file in temp directory
        test_file = temp_directory / "test.txt"
        test_file.write_text("test content")
        
        assert test_file.exists()
        
        # Cleanup
        git_sync_service.cleanup_all_temp_dirs()
        
        assert len(git_sync_service.temp_dirs) == 0
        assert not temp_directory.exists()


class TestGitSyncResult:
    """Test cases for GitSyncResult."""
    
    def test_git_sync_result_creation(self):
        """Test creating GitSyncResult."""
        result = GitSyncResult(
            success=True,
            message="Sync completed",
            operation_id="sync_123",
            files_exported=10,
            files_changed=5,
            commit_hash="abc123"
        )
        
        assert result.success is True
        assert result.message == "Sync completed"
        assert result.operation_id == "sync_123"
        assert result.files_exported == 10
        assert result.files_changed == 5
        assert result.commit_hash == "abc123"
        assert result.errors == []
    
    def test_git_sync_result_with_errors(self):
        """Test creating GitSyncResult with errors."""
        errors = ["Error 1", "Error 2"]
        
        result = GitSyncResult(
            success=False,
            message="Sync failed",
            operation_id="sync_456",
            files_exported=0,
            files_changed=0,
            errors=errors
        )
        
        assert result.success is False
        assert result.message == "Sync failed"
        assert result.errors == errors


class TestGitConfig:
    """Test cases for GitConfig."""
    
    def test_git_config_creation(self):
        """Test creating GitConfig."""
        config = GitConfig(
            repo_url="https://github.com/test/repo.git",
            branch="develop",
            username="testuser",
            password="testpass",
            commit_author_name="Test User",
            commit_author_email="test@example.com",
            auto_push=False,
            auto_pull=False
        )
        
        assert config.repo_url == "https://github.com/test/repo.git"
        assert config.branch == "develop"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.commit_author_name == "Test User"
        assert config.commit_author_email == "test@example.com"
        assert config.auto_push is False
        assert config.auto_pull is False
    
    def test_git_config_defaults(self):
        """Test GitConfig with default values."""
        config = GitConfig(repo_url="https://github.com/test/repo.git")
        
        assert config.branch == "main"
        assert config.username is None
        assert config.password is None
        assert config.ssh_key_path is None
        assert config.commit_author_name == "AI Agent"
        assert config.commit_author_email == "ai-agent@example.com"
        assert config.auto_push is True
        assert config.auto_pull is True