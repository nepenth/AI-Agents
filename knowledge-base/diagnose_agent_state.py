#!/usr/bin/env python3
"""
Diagnostic script to check agent state and identify issues
Run this from the Flask app directory: python diagnose_agent_state.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def diagnose_agent_state():
    """Diagnose current agent state"""
    try:
        from knowledge_base_agent.models import db, AgentState, CeleryTaskState
        from knowledge_base_agent.web import get_or_create_agent_state
        from knowledge_base_agent import create_app
        
        # Create app context
        app = create_app()
        with app.app_context():
            print("🔍 Diagnosing Agent State")
            print("=" * 50)
            
            # Check AgentState
            agent_state = get_or_create_agent_state()
            print(f"📊 AgentState:")
            print(f"  - is_running: {agent_state.is_running}")
            print(f"  - current_task_id: {agent_state.current_task_id}")
            print(f"  - current_phase_message: {agent_state.current_phase_message}")
            print(f"  - last_update: {agent_state.last_update}")
            
            # Check CeleryTaskState
            if agent_state.current_task_id:
                task = CeleryTaskState.query.filter_by(task_id=agent_state.current_task_id).first()
                if task:
                    print(f"\n📊 CeleryTaskState for {agent_state.current_task_id}:")
                    print(f"  - status: {task.status}")
                    print(f"  - current_phase_id: {task.current_phase_id}")
                    print(f"  - current_phase_message: {task.current_phase_message}")
                    print(f"  - progress_percentage: {task.progress_percentage}")
                    print(f"  - created_at: {task.created_at}")
                    print(f"  - updated_at: {task.updated_at}")
                    print(f"  - human_readable_name: {task.human_readable_name}")
                else:
                    print(f"\n❌ No CeleryTaskState found for task_id: {agent_state.current_task_id}")
            
            # Check all recent tasks
            recent_tasks = CeleryTaskState.query.order_by(CeleryTaskState.created_at.desc()).limit(5).all()
            print(f"\n📊 Recent Tasks ({len(recent_tasks)}):")
            for task in recent_tasks:
                status_icon = "🟢" if task.status in ['PROGRESS', 'STARTED'] else "🔴" if task.status in ['FAILURE'] else "🟡"
                print(f"  {status_icon} {task.task_id[:8]}... - {task.status} - {task.current_phase_message or 'No message'}")
            
            # Test API endpoint simulation
            print(f"\n🧪 Simulating /agent/status endpoint:")
            if not agent_state.current_task_id:
                print("  Result: {'is_running': False, 'status': 'IDLE'}")
            else:
                task = CeleryTaskState.query.filter_by(task_id=agent_state.current_task_id).first()
                if not task:
                    print("  Result: Task not found - would clear stale state")
                elif task.status in ['SUCCESS', 'FAILURE', 'REVOKED']:
                    print(f"  Result: Task in terminal state ({task.status}) - would clear state")
                else:
                    print("  Result: Would return running status with task details")
                    print(f"    - task_id: {task.task_id}")
                    print(f"    - current_phase_message: {task.current_phase_message}")
                    print(f"    - progress: {task.progress_percentage or 0}%")
                    if task.current_phase_id:
                        print(f"    - progress.phase_id: {task.current_phase_id}")
            
            print(f"\n✅ Diagnosis complete")
            
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_agent_state()