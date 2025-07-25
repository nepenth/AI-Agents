#!/usr/bin/env python3
"""
Debug script to test agent status detection and identify issues
"""

import requests
import json
import sys
from datetime import datetime

def test_agent_status():
    """Test the main agent status endpoint"""
    print("🔍 Testing /agent/status endpoint...")
    
    try:
        response = requests.get('http://localhost:5000/agent/status')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success!")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"❌ Error {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def test_task_status(task_id):
    """Test the detailed task status endpoint"""
    print(f"\n🔍 Testing /v2/agent/status/{task_id} endpoint...")
    
    try:
        response = requests.get(f'http://localhost:5000/v2/agent/status/{task_id}')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success!")
            print(json.dumps(data, indent=2))
            return data
        else:
            print(f"❌ Error {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def test_database_query():
    """Test direct database query to see task state"""
    print(f"\n🔍 Testing database state...")
    
    try:
        # This would need to be run from within the Flask app context
        print("Note: Database query needs to be run from Flask app context")
        print("You can run this in the Flask shell:")
        print("from knowledge_base_agent.models import CeleryTaskState")
        print("tasks = CeleryTaskState.query.all()")
        print("for task in tasks: print(f'{task.task_id}: {task.status} - {task.current_phase_message}')")
        
    except Exception as e:
        print(f"❌ Exception: {e}")

def main():
    print("🚀 Agent Status Debug Tool")
    print("=" * 50)
    
    # Test 1: Basic agent status
    agent_status = test_agent_status()
    
    if agent_status and agent_status.get('is_running') and agent_status.get('task_id'):
        task_id = agent_status['task_id']
        print(f"\n📊 Found running task: {task_id}")
        
        # Test 2: Detailed task status
        task_status = test_task_status(task_id)
        
        if task_status:
            print(f"\n📊 Analysis:")
            print(f"  - Task ID: {task_status.get('task_id')}")
            print(f"  - Is Running: {task_status.get('is_running')}")
            print(f"  - Status: {task_status.get('status')}")
            print(f"  - Phase Message: {task_status.get('current_phase_message')}")
            
            if 'progress' in task_status:
                progress = task_status['progress']
                print(f"  - Progress Phase ID: {progress.get('phase_id')}")
                print(f"  - Progress Message: {progress.get('message')}")
                print(f"  - Progress Percentage: {progress.get('progress')}")
        
    else:
        print("\n💤 No running task detected")
    
    # Test 3: Database state
    test_database_query()
    
    print(f"\n🏁 Debug complete at {datetime.now()}")

if __name__ == "__main__":
    main()