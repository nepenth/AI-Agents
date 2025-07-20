#!/usr/bin/env python3
"""
Enhanced script to detect and clean up stale agent tasks.
Run this periodically to detect tasks that are marked as running but have no active Celery worker.

This script now includes comprehensive state validation across all state management systems.
"""

import sys
from datetime import datetime, timedelta
from knowledge_base_agent.models import AgentState, CeleryTaskState, db
from knowledge_base_agent.web import app
from knowledge_base_agent.celery_app import celery_app
import redis

def check_stale_tasks():
    """Check for stale tasks and optionally clean them up."""
    
    with app.app_context():
        print("🔍 COMPREHENSIVE STALE TASK DETECTION")
        print("=" * 50)
        
        # Get current agent state
        agent_state = AgentState.query.first()
        
        if not agent_state:
            print("❌ No AgentState record found in database")
            return
        
        if not agent_state.is_running:
            print("✅ No agent currently running according to AgentState")
            
            # Check for orphaned CeleryTaskState records
            orphaned_tasks = CeleryTaskState.query.filter(
                CeleryTaskState.status.in_(['PROGRESS', 'PENDING'])
            ).all()
            
            if orphaned_tasks:
                print(f"⚠️  Found {len(orphaned_tasks)} orphaned CeleryTaskState records")
                for task in orphaned_tasks:
                    print(f"   - Task {task.task_id}: {task.status} since {task.updated_at}")
                
                if len(sys.argv) > 1 and sys.argv[1] == '--clean':
                    print("🧹 Cleaning up orphaned CeleryTaskState records...")
                    for task in orphaned_tasks:
                        task.status = 'FAILURE'
                        task.completed_at = datetime.utcnow()
                        task.updated_at = datetime.utcnow()
                        task.error_message = 'Task was orphaned - cleaned up by stale task detector'
                    db.session.commit()
                    print("✅ Orphaned tasks cleaned up")
            
            return
        
        print(f"🔍 Agent marked as running: {agent_state.current_phase_message}")
        print(f"📅 Last update: {agent_state.last_update}")
        print(f"🆔 Task ID: {agent_state.current_task_id}")
        
        # Check CeleryTaskState consistency
        celery_task_state = None
        if agent_state.current_task_id:
            celery_task_state = CeleryTaskState.query.filter_by(
                task_id=agent_state.current_task_id
            ).first()
            
            if celery_task_state:
                print(f"📋 CeleryTaskState: {celery_task_state.status} (Celery ID: {celery_task_state.celery_task_id})")
            else:
                print("❌ No CeleryTaskState record found for current task")
        
        # Check if task is actually running in Celery
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        
        is_stale = False
        celery_task_found = False
        
        if not active_tasks:
            print("❌ No active Celery tasks found")
            is_stale = True
        else:
            print(f"🔍 Found active tasks on {len(active_tasks)} workers")
            
            # Check if our specific task is in the active tasks
            for worker, tasks in active_tasks.items():
                print(f"   Worker {worker}: {len(tasks)} active tasks")
                for task in tasks:
                    if (task.get('id') == agent_state.current_task_id or 
                        (celery_task_state and task.get('id') == celery_task_state.celery_task_id)):
                        celery_task_found = True
                        print(f"✅ Task found running on worker: {worker}")
                        print(f"   Task name: {task.get('name', 'unknown')}")
                        break
            
            if not celery_task_found:
                print("❌ Agent task not found in active Celery tasks")
                is_stale = True
        
        # Check how long it's been running
        if agent_state.last_update:
            time_running = datetime.utcnow() - agent_state.last_update
            print(f"⏱️  Running for: {time_running}")
            
            if time_running > timedelta(hours=2):
                print("⚠️  Task has been running for over 2 hours - likely stale")
                is_stale = True
        
        # Check Redis state consistency
        try:
            r_progress = redis.Redis.from_url('redis://localhost:6379/1', decode_responses=True)
            r_logs = redis.Redis.from_url('redis://localhost:6379/2', decode_responses=True)
            
            if agent_state.current_task_id:
                progress_key = f"progress:{agent_state.current_task_id}"
                logs_key = f"logs:{agent_state.current_task_id}"
                
                progress_exists = r_progress.exists(progress_key)
                logs_exist = r_logs.exists(logs_key)
                
                print(f"📊 Redis state - Progress: {'✅' if progress_exists else '❌'}, Logs: {'✅' if logs_exist else '❌'}")
                
                if progress_exists:
                    progress_data = r_progress.hgetall(progress_key)
                    print(f"   Progress: {progress_data.get('progress', 'unknown')}% - {progress_data.get('message', 'no message')}")
        except Exception as e:
            print(f"⚠️  Could not check Redis state: {e}")
        
        # Determine if cleanup is needed
        if is_stale:
            print("\n🧹 STALE TASK DETECTED")
            print("Issues found:")
            if not celery_task_found:
                print("  - Task not found in active Celery tasks")
            if agent_state.last_update and (datetime.utcnow() - agent_state.last_update) > timedelta(hours=2):
                print("  - Task has been running for over 2 hours")
            
            if len(sys.argv) > 1 and sys.argv[1] == '--clean':
                print("\n🧹 Cleaning up stale state...")
                
                # Clean up AgentState
                old_task_id = agent_state.current_task_id
                agent_state.is_running = False
                agent_state.current_task_id = None
                agent_state.current_phase_message = 'Idle'
                agent_state.last_update = datetime.utcnow()
                
                # Clean up CeleryTaskState
                if celery_task_state:
                    celery_task_state.status = 'FAILURE'
                    celery_task_state.completed_at = datetime.utcnow()
                    celery_task_state.updated_at = datetime.utcnow()
                    celery_task_state.error_message = 'Task was stale - cleaned up by stale task detector'
                
                db.session.commit()
                
                # Clean up Redis
                if old_task_id:
                    try:
                        progress_key = f"progress:{old_task_id}"
                        logs_key = f"logs:{old_task_id}"
                        
                        deleted_progress = r_progress.delete(progress_key)
                        deleted_logs = r_logs.delete(logs_key)
                        
                        print(f"   Cleaned Redis: {deleted_progress} progress keys, {deleted_logs} log keys")
                    except Exception as e:
                        print(f"   Redis cleanup failed: {e}")
                
                print("✅ Stale state cleaned up successfully")
                print("   - AgentState: is_running=False")
                print("   - CeleryTaskState: status=FAILURE")
                print("   - Redis: progress and log data cleared")
            else:
                print("\n💡 Run with --clean flag to clean up stale state")
                print("   python3 check_stale_tasks.py --clean")
        else:
            print("\n✅ Task appears to be running normally")
            print("All state systems are consistent:")
            print("  - AgentState shows task running")
            print("  - CeleryTaskState exists and matches")
            print("  - Celery worker has active task")
            print("  - Redis state is present")

def show_system_status():
    """Show comprehensive system status."""
    with app.app_context():
        print("📊 SYSTEM STATUS OVERVIEW")
        print("=" * 50)
        
        # AgentState
        agent_state = AgentState.query.first()
        if agent_state:
            print(f"AgentState: {'🟢 Running' if agent_state.is_running else '⚪ Idle'}")
            if agent_state.is_running:
                print(f"  Task ID: {agent_state.current_task_id}")
                print(f"  Phase: {agent_state.current_phase_message}")
                print(f"  Last Update: {agent_state.last_update}")
        else:
            print("AgentState: ❌ No record found")
        
        # CeleryTaskState
        active_celery_tasks = CeleryTaskState.query.filter(
            CeleryTaskState.status.in_(['PROGRESS', 'PENDING'])
        ).count()
        total_celery_tasks = CeleryTaskState.query.count()
        print(f"CeleryTaskState: {active_celery_tasks} active, {total_celery_tasks} total")
        
        # Celery Workers
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            if active_tasks:
                total_active = sum(len(tasks) for tasks in active_tasks.values())
                print(f"Celery Workers: {len(active_tasks)} workers, {total_active} active tasks")
            else:
                print("Celery Workers: ❌ No active workers or tasks")
        except Exception as e:
            print(f"Celery Workers: ❌ Cannot connect ({e})")
        
        # Redis
        try:
            r_progress = redis.Redis.from_url('redis://localhost:6379/1', decode_responses=True)
            r_logs = redis.Redis.from_url('redis://localhost:6379/2', decode_responses=True)
            
            progress_keys = len(r_progress.keys("progress:*"))
            log_keys = len(r_logs.keys("logs:*"))
            print(f"Redis: {progress_keys} progress keys, {log_keys} log keys")
        except Exception as e:
            print(f"Redis: ❌ Cannot connect ({e})")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        show_system_status()
    else:
        check_stale_tasks()