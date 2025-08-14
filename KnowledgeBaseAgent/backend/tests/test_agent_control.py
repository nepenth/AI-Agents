"""Tests for agent control system."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.services.agent_control import (
    AgentControlService,
    AgentTaskConfig,
    AgentTaskType,
    AgentTaskStatus,
    AgentTaskInfo
)


@pytest.fixture
def agent_service():
    """Create agent control service for testing."""
    return AgentControlService()


@pytest.fixture
def sample_task_config():
    """Create sample task configuration."""
    return AgentTaskConfig(
        task_type=AgentTaskType.CONTENT_FETCHING,
        parameters={"sources": ["http://example.com"]},
        priority=5,
        timeout=300,
        retry_count=3
    )


class TestAgentControlService:
    """Test cases for AgentControlService."""
    
    @pytest.mark.asyncio
    async def test_start_task_success(self, agent_service, sample_task_config):
        """Test successful task start."""
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification') as mock_notify:
                mock_notify.return_value = None
                
                task_id = await agent_service.start_task(sample_task_config)
                
                assert task_id is not None
                assert task_id in agent_service.active_tasks
                
                task_info = agent_service.active_tasks[task_id]
                assert task_info.task_type == AgentTaskType.CONTENT_FETCHING
                assert task_info.status == AgentTaskStatus.RUNNING
                assert task_info.celery_task_id == "celery-task-123"
                assert task_info.started_at is not None
                
                mock_celery.assert_called_once_with(sample_task_config)
                mock_notify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_task_failure(self, agent_service, sample_task_config):
        """Test task start failure."""
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery.side_effect = Exception("Celery error")
            
            with pytest.raises(Exception, match="Celery error"):
                await agent_service.start_task(sample_task_config)
    
    @pytest.mark.asyncio
    async def test_stop_task_success(self, agent_service, sample_task_config):
        """Test successful task stop."""
        # Start a task first
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification'):
                task_id = await agent_service.start_task(sample_task_config)
        
        # Now stop the task
        with patch('app.services.agent_control.celery_app.control.revoke') as mock_revoke:
            with patch.object(agent_service.notification_service, 'send_notification') as mock_notify:
                mock_notify.return_value = None
                
                success = await agent_service.stop_task(task_id)
                
                assert success is True
                assert task_id not in agent_service.active_tasks
                assert len(agent_service.task_history) == 1
                
                stopped_task = agent_service.task_history[0]
                assert stopped_task.status == AgentTaskStatus.CANCELLED
                assert stopped_task.completed_at is not None
                
                mock_revoke.assert_called_once_with("celery-task-123", terminate=True)
                mock_notify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_nonexistent_task(self, agent_service):
        """Test stopping a non-existent task."""
        success = await agent_service.stop_task("nonexistent-task-id")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_get_task_status_active(self, agent_service, sample_task_config):
        """Test getting status of active task."""
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification'):
                task_id = await agent_service.start_task(sample_task_config)
        
        task_info = await agent_service.get_task_status(task_id)
        
        assert task_info is not None
        assert task_info.task_id == task_id
        assert task_info.status == AgentTaskStatus.RUNNING
        assert task_info.task_type == AgentTaskType.CONTENT_FETCHING
    
    @pytest.mark.asyncio
    async def test_get_task_status_history(self, agent_service, sample_task_config):
        """Test getting status of task in history."""
        # Create and complete a task
        task_info = AgentTaskInfo(
            task_id="test-task-123",
            task_type=AgentTaskType.CONTENT_FETCHING,
            status=AgentTaskStatus.COMPLETED,
            config=sample_task_config,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        agent_service.task_history.append(task_info)
        
        retrieved_task = await agent_service.get_task_status("test-task-123")
        
        assert retrieved_task is not None
        assert retrieved_task.task_id == "test-task-123"
        assert retrieved_task.status == AgentTaskStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, agent_service):
        """Test getting status of non-existent task."""
        task_info = await agent_service.get_task_status("nonexistent-task")
        assert task_info is None
    
    @pytest.mark.asyncio
    async def test_list_active_tasks(self, agent_service, sample_task_config):
        """Test listing active tasks."""
        # Start multiple tasks
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification'):
                task_id1 = await agent_service.start_task(sample_task_config)
                task_id2 = await agent_service.start_task(sample_task_config)
        
        active_tasks = await agent_service.list_active_tasks()
        
        assert len(active_tasks) == 2
        task_ids = [task.task_id for task in active_tasks]
        assert task_id1 in task_ids
        assert task_id2 in task_ids
    
    @pytest.mark.asyncio
    async def test_list_task_history_with_filters(self, agent_service):
        """Test listing task history with filters."""
        # Create sample history
        now = datetime.utcnow()
        
        tasks = [
            AgentTaskInfo(
                task_id="task-1",
                task_type=AgentTaskType.CONTENT_FETCHING,
                status=AgentTaskStatus.COMPLETED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
                created_at=now - timedelta(hours=1),
                completed_at=now
            ),
            AgentTaskInfo(
                task_id="task-2",
                task_type=AgentTaskType.CONTENT_PROCESSING,
                status=AgentTaskStatus.FAILED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_PROCESSING, parameters={}),
                created_at=now - timedelta(hours=2),
                completed_at=now
            ),
            AgentTaskInfo(
                task_id="task-3",
                task_type=AgentTaskType.CONTENT_FETCHING,
                status=AgentTaskStatus.COMPLETED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
                created_at=now - timedelta(hours=3),
                completed_at=now
            )
        ]
        
        agent_service.task_history.extend(tasks)
        
        # Test filter by task type
        fetching_tasks = await agent_service.list_task_history(
            limit=10,
            task_type=AgentTaskType.CONTENT_FETCHING
        )
        assert len(fetching_tasks) == 2
        assert all(task.task_type == AgentTaskType.CONTENT_FETCHING for task in fetching_tasks)
        
        # Test filter by status
        failed_tasks = await agent_service.list_task_history(
            limit=10,
            status=AgentTaskStatus.FAILED
        )
        assert len(failed_tasks) == 1
        assert failed_tasks[0].status == AgentTaskStatus.FAILED
        
        # Test limit
        limited_tasks = await agent_service.list_task_history(limit=2)
        assert len(limited_tasks) == 2
        
        # Tasks should be sorted by creation time (newest first)
        assert limited_tasks[0].created_at > limited_tasks[1].created_at
    
    @pytest.mark.asyncio
    async def test_get_system_metrics(self, agent_service):
        """Test getting system metrics."""
        with patch('app.services.agent_control.celery_app.control.inspect') as mock_inspect:
            mock_inspector = Mock()
            mock_inspector.stats.return_value = {"worker1": {"pool": {"max-concurrency": 4}}}
            mock_inspector.active.return_value = {"worker1": [{"id": "task1"}]}
            mock_inspect.return_value = mock_inspector
            
            metrics = await agent_service.get_system_metrics()
            
            assert "timestamp" in metrics
            assert "celery" in metrics
            assert "agent" in metrics
            assert "system" in metrics
            
            assert metrics["celery"]["total_workers"] == 1
            assert metrics["celery"]["active_tasks"] == 1
            assert metrics["agent"]["active_tasks"] == 0  # No active tasks in test
    
    @pytest.mark.asyncio
    async def test_get_system_metrics_error(self, agent_service):
        """Test getting system metrics with error."""
        with patch('app.services.agent_control.celery_app.control.inspect') as mock_inspect:
            mock_inspect.side_effect = Exception("Celery connection error")
            
            metrics = await agent_service.get_system_metrics()
            
            assert "error" in metrics
            assert "timestamp" in metrics
    
    @pytest.mark.asyncio
    async def test_schedule_task(self, agent_service, sample_task_config):
        """Test scheduling a task."""
        schedule_id = await agent_service.schedule_task(sample_task_config, "0 */6 * * *")
        
        assert schedule_id is not None
        assert sample_task_config.schedule == "0 */6 * * *"
    
    @pytest.mark.asyncio
    async def test_update_task_progress(self, agent_service, sample_task_config):
        """Test updating task progress."""
        # Start a task first
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification'):
                task_id = await agent_service.start_task(sample_task_config)
        
        # Update progress
        progress = {"completed": 50, "total": 100, "status": "processing"}
        
        with patch.object(agent_service.notification_service, 'notify_task_progress') as mock_notify:
            mock_notify.return_value = None
            
            await agent_service.update_task_progress(task_id, progress)
            
            task_info = agent_service.active_tasks[task_id]
            assert task_info.progress == progress
            
            mock_notify.assert_called_once_with(task_id, progress)
    
    @pytest.mark.asyncio
    async def test_complete_task(self, agent_service, sample_task_config):
        """Test completing a task."""
        # Start a task first
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification'):
                task_id = await agent_service.start_task(sample_task_config)
        
        # Complete the task
        result = {"processed_items": 10, "success": True}
        
        with patch.object(agent_service.notification_service, 'notify_task_completion') as mock_notify_complete:
            with patch.object(agent_service.notification_service, 'send_notification') as mock_notify:
                mock_notify_complete.return_value = None
                mock_notify.return_value = None
                
                await agent_service.complete_task(task_id, result)
                
                assert task_id not in agent_service.active_tasks
                assert len(agent_service.task_history) == 1
                
                completed_task = agent_service.task_history[0]
                assert completed_task.status == AgentTaskStatus.COMPLETED
                assert completed_task.result == result
                assert completed_task.completed_at is not None
                
                mock_notify_complete.assert_called_once_with(task_id, result)
                mock_notify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fail_task(self, agent_service, sample_task_config):
        """Test failing a task."""
        # Start a task first
        with patch.object(agent_service, '_start_celery_task') as mock_celery:
            mock_celery_task = Mock()
            mock_celery_task.id = "celery-task-123"
            mock_celery.return_value = mock_celery_task
            
            with patch.object(agent_service.notification_service, 'send_notification'):
                task_id = await agent_service.start_task(sample_task_config)
        
        # Fail the task
        error_message = "Processing failed due to network error"
        
        with patch.object(agent_service.notification_service, 'notify_task_failure') as mock_notify_fail:
            with patch.object(agent_service.notification_service, 'send_notification') as mock_notify:
                mock_notify_fail.return_value = None
                mock_notify.return_value = None
                
                await agent_service.fail_task(task_id, error_message)
                
                assert task_id not in agent_service.active_tasks
                assert len(agent_service.task_history) == 1
                
                failed_task = agent_service.task_history[0]
                assert failed_task.status == AgentTaskStatus.FAILED
                assert failed_task.error == error_message
                assert failed_task.completed_at is not None
                
                mock_notify_fail.assert_called_once_with(task_id, {"error": error_message})
                mock_notify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_tasks(self, agent_service):
        """Test cleaning up old tasks."""
        now = datetime.utcnow()
        
        # Create tasks with different ages
        old_task = AgentTaskInfo(
            task_id="old-task",
            task_type=AgentTaskType.CONTENT_FETCHING,
            status=AgentTaskStatus.COMPLETED,
            config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
            created_at=now - timedelta(days=10),
            completed_at=now - timedelta(days=10)
        )
        
        recent_task = AgentTaskInfo(
            task_id="recent-task",
            task_type=AgentTaskType.CONTENT_FETCHING,
            status=AgentTaskStatus.COMPLETED,
            config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
            created_at=now - timedelta(days=2),
            completed_at=now - timedelta(days=2)
        )
        
        agent_service.task_history.extend([old_task, recent_task])
        
        with patch.object(agent_service.notification_service, 'send_notification') as mock_notify:
            mock_notify.return_value = None
            
            cleaned_count = await agent_service.cleanup_old_tasks(days_old=7)
            
            assert cleaned_count == 1
            assert len(agent_service.task_history) == 1
            assert agent_service.task_history[0].task_id == "recent-task"
            
            mock_notify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_task_statistics(self, agent_service):
        """Test getting task statistics."""
        now = datetime.utcnow()
        
        # Create sample task history
        tasks = [
            AgentTaskInfo(
                task_id="task-1",
                task_type=AgentTaskType.CONTENT_FETCHING,
                status=AgentTaskStatus.COMPLETED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
                created_at=now - timedelta(hours=2),
                started_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=1, minutes=30)
            ),
            AgentTaskInfo(
                task_id="task-2",
                task_type=AgentTaskType.CONTENT_PROCESSING,
                status=AgentTaskStatus.FAILED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_PROCESSING, parameters={}),
                created_at=now - timedelta(hours=1),
                started_at=now - timedelta(hours=1),
                completed_at=now - timedelta(minutes=30)
            ),
            AgentTaskInfo(
                task_id="task-3",
                task_type=AgentTaskType.CONTENT_FETCHING,
                status=AgentTaskStatus.COMPLETED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
                created_at=now - timedelta(minutes=30),
                started_at=now - timedelta(minutes=30),
                completed_at=now - timedelta(minutes=15)
            )
        ]
        
        agent_service.task_history.extend(tasks)
        
        stats = await agent_service.get_task_statistics()
        
        assert stats["total_tasks"] == 3
        assert stats["success_rate"] == 0.667  # 2 out of 3 completed
        assert stats["average_duration_seconds"] > 0
        assert stats["task_type_distribution"]["content_fetching"] == 2
        assert stats["task_type_distribution"]["content_processing"] == 1
        assert stats["status_distribution"]["completed"] == 2
        assert stats["status_distribution"]["failed"] == 1
        assert stats["active_tasks"] == 0
    
    @pytest.mark.asyncio
    async def test_get_task_statistics_empty(self, agent_service):
        """Test getting task statistics with no history."""
        stats = await agent_service.get_task_statistics()
        
        assert stats["total_tasks"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["average_duration"] == 0.0
        assert stats["task_type_distribution"] == {}
        assert stats["status_distribution"] == {}
    
    def test_move_to_history(self, agent_service, sample_task_config):
        """Test moving task from active to history."""
        # Create a task info
        task_info = AgentTaskInfo(
            task_id="test-task",
            task_type=AgentTaskType.CONTENT_FETCHING,
            status=AgentTaskStatus.RUNNING,
            config=sample_task_config,
            created_at=datetime.utcnow()
        )
        
        agent_service.active_tasks["test-task"] = task_info
        
        # Move to history
        agent_service._move_to_history("test-task")
        
        assert "test-task" not in agent_service.active_tasks
        assert len(agent_service.task_history) == 1
        assert agent_service.task_history[0].task_id == "test-task"
    
    def test_move_to_history_with_limit(self, agent_service):
        """Test moving task to history with size limit."""
        # Fill history to max size
        for i in range(agent_service.max_history_size):
            task_info = AgentTaskInfo(
                task_id=f"task-{i}",
                task_type=AgentTaskType.CONTENT_FETCHING,
                status=AgentTaskStatus.COMPLETED,
                config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
                created_at=datetime.utcnow()
            )
            agent_service.task_history.append(task_info)
        
        # Add one more task to active
        new_task = AgentTaskInfo(
            task_id="new-task",
            task_type=AgentTaskType.CONTENT_FETCHING,
            status=AgentTaskStatus.COMPLETED,
            config=AgentTaskConfig(task_type=AgentTaskType.CONTENT_FETCHING, parameters={}),
            created_at=datetime.utcnow()
        )
        agent_service.active_tasks["new-task"] = new_task
        
        # Move to history (should trigger size limit)
        agent_service._move_to_history("new-task")
        
        assert len(agent_service.task_history) == agent_service.max_history_size
        assert agent_service.task_history[-1].task_id == "new-task"


class TestAgentTaskConfig:
    """Test cases for AgentTaskConfig."""
    
    def test_task_config_creation(self):
        """Test creating task configuration."""
        config = AgentTaskConfig(
            task_type=AgentTaskType.CONTENT_FETCHING,
            parameters={"sources": ["http://example.com"]},
            priority=8,
            timeout=600,
            retry_count=5,
            schedule="0 */4 * * *"
        )
        
        assert config.task_type == AgentTaskType.CONTENT_FETCHING
        assert config.parameters == {"sources": ["http://example.com"]}
        assert config.priority == 8
        assert config.timeout == 600
        assert config.retry_count == 5
        assert config.schedule == "0 */4 * * *"
    
    def test_task_config_defaults(self):
        """Test task configuration with default values."""
        config = AgentTaskConfig(
            task_type=AgentTaskType.CONTENT_PROCESSING,
            parameters={}
        )
        
        assert config.priority == 5
        assert config.timeout is None
        assert config.retry_count == 3
        assert config.schedule is None


class TestAgentTaskInfo:
    """Test cases for AgentTaskInfo."""
    
    def test_task_info_creation(self):
        """Test creating task info."""
        config = AgentTaskConfig(
            task_type=AgentTaskType.CONTENT_FETCHING,
            parameters={}
        )
        
        now = datetime.utcnow()
        task_info = AgentTaskInfo(
            task_id="test-task-123",
            task_type=AgentTaskType.CONTENT_FETCHING,
            status=AgentTaskStatus.RUNNING,
            config=config,
            created_at=now,
            started_at=now,
            progress={"completed": 25, "total": 100}
        )
        
        assert task_info.task_id == "test-task-123"
        assert task_info.task_type == AgentTaskType.CONTENT_FETCHING
        assert task_info.status == AgentTaskStatus.RUNNING
        assert task_info.config == config
        assert task_info.created_at == now
        assert task_info.started_at == now
        assert task_info.progress == {"completed": 25, "total": 100}
        assert task_info.completed_at is None
        assert task_info.result is None
        assert task_info.error is None