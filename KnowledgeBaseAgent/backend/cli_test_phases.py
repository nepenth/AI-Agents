#!/usr/bin/env python3
"""
CLI script for testing individual phases of the AI processing pipeline.
"""
import asyncio
import sys
import json
import argparse
from typing import Dict, Any, Optional
import requests
from datetime import datetime

# Base URL for the API (adjust as needed)
BASE_URL = "http://localhost:8000/api/v1"


def make_request(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make HTTP request to the API."""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=data)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response text: {e.response.text}")
        sys.exit(1)


def create_test_bookmark(tweet_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Create a test Twitter bookmark."""
    print(f"🔄 Creating Twitter bookmark for tweet {tweet_id}...")
    
    data = {
        "tweet_id": tweet_id,
        "force_refresh": force_refresh
    }
    
    result = make_request("POST", "/content/twitter/bookmark", data)
    print(f"✅ Created bookmark: {result['id']}")
    return result


def test_phase(content_id: str, phase_name: str, force: bool = False) -> Dict[str, Any]:
    """Test a specific phase."""
    print(f"🔄 Testing phase '{phase_name}' for content {content_id}...")
    
    params = {
        "item_id": content_id,
        "force": force
    }
    
    result = make_request("POST", f"/content/test/phase/{phase_name}", params)
    print(f"✅ Phase test result: {result.get('message', 'Completed')}")
    return result


def get_content_item(content_id: str) -> Dict[str, Any]:
    """Get content item details."""
    print(f"🔍 Getting content item {content_id}...")
    
    result = make_request("GET", f"/content/items/{content_id}")
    return result


def get_subphase_status(content_id: str) -> Dict[str, Any]:
    """Get sub-phase status for content item."""
    print(f"📊 Getting sub-phase status for {content_id}...")
    
    result = make_request("GET", f"/content/items/{content_id}/subphases")
    return result


def update_subphase_status(content_id: str, phase: str, status: bool, model_used: Optional[str] = None, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update sub-phase status."""
    print(f"🔄 Updating {phase} status to {status} for {content_id}...")
    
    data = {
        "phase": phase,
        "status": status,
        "model_used": model_used,
        "results": results
    }
    
    result = make_request("PUT", f"/content/items/{content_id}/subphases", data)
    print(f"✅ Updated sub-phase status")
    return result


def print_content_summary(content: Dict[str, Any]):
    """Print a summary of content item."""
    print(f"\n📄 Content Summary:")
    print(f"   ID: {content['id']}")
    print(f"   Title: {content['title']}")
    print(f"   Source: {content['source_type']} ({content.get('tweet_id', content['source_id'])})")
    print(f"   Author: {content.get('author_username', 'N/A')}")
    print(f"   Processing State: {content['processing_state']}")
    print(f"   Is Twitter Content: {content.get('is_twitter_content', False)}")
    print(f"   Is Thread: {content.get('is_thread', False)}")
    print(f"   Has Media: {content['has_media']}")
    print(f"   Total Engagement: {content.get('total_engagement', 0)}")
    print(f"   Sub-phase Completion: {content.get('sub_phase_completion_percentage', 0):.1f}%")
    print(f"   Created: {content['created_at']}")


def print_subphase_status(status: Dict[str, Any]):
    """Print sub-phase status."""
    print(f"\n📊 Sub-phase Status:")
    print(f"   Bookmark Cached: {'✅' if status['bookmark_cached'] else '❌'}")
    print(f"   Media Analyzed: {'✅' if status['media_analyzed'] else '❌'}")
    print(f"   Content Understood: {'✅' if status['content_understood'] else '❌'}")
    print(f"   Categorized: {'✅' if status['categorized'] else '❌'}")
    print(f"   Completion: {status['completion_percentage']:.1f}%")
    print(f"   Last Updated: {status['last_updated']}")


def test_pipeline_components() -> Dict[str, Any]:
    """Test pipeline components availability."""
    print("🔍 Testing pipeline components...")
    
    result = make_request("GET", "/pipeline/test-components")
    return result


def process_bookmark(tweet_id: str, force_refresh: bool = False, models_override: Optional[Dict[str, Any]] = None, run_async: bool = True) -> Dict[str, Any]:
    """Process a Twitter bookmark through the pipeline."""
    print(f"🔄 Processing bookmark for tweet {tweet_id}...")
    
    data = {
        "tweet_id": tweet_id,
        "force_refresh": force_refresh,
        "models_override": models_override,
        "run_async": run_async
    }
    
    result = make_request("POST", "/pipeline/process-bookmark", data)
    print(f"✅ Bookmark processing: {result['status']}")
    return result


def fetch_bookmarks(collection_url: Optional[str] = None, max_results: int = 100, force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch bookmarks from Twitter collection."""
    print(f"🔄 Fetching bookmarks (max: {max_results})...")
    
    data = {
        "collection_url": collection_url,
        "max_results": max_results,
        "force_refresh": force_refresh
    }
    
    result = make_request("POST", "/pipeline/fetch-bookmarks", data)
    print(f"✅ Fetched {result['fetched_count']} bookmarks, skipped {result['skipped_count']}, failed {result['failed_count']}")
    return result


def generate_synthesis(models_override: Optional[Dict[str, Any]] = None, min_bookmarks: int = 3) -> Dict[str, Any]:
    """Generate synthesis documents."""
    print(f"🔄 Generating synthesis documents (min bookmarks: {min_bookmarks})...")
    
    data = {
        "models_override": models_override,
        "min_bookmarks_per_category": min_bookmarks
    }
    
    result = make_request("POST", "/pipeline/generate-synthesis", data)
    print(f"✅ Generated {result['generated_count']} synthesis documents, skipped {result['skipped_count']}")
    return result


def execute_seven_phase_pipeline(config: Dict[str, Any], models_override: Optional[Dict[str, Any]] = None, run_async: bool = True) -> Dict[str, Any]:
    """Execute the seven-phase pipeline."""
    print("🚀 Executing seven-phase pipeline...")
    
    data = {
        "config": config,
        "models_override": models_override,
        "run_async": run_async
    }
    
    result = make_request("POST", "/pipeline/execute-seven-phase", data)
    print(f"✅ Pipeline execution: {result['status']}")
    return result


def get_pipeline_status(pipeline_id: str) -> Dict[str, Any]:
    """Get pipeline execution status."""
    print(f"🔍 Getting pipeline status for {pipeline_id}...")
    
    result = make_request("GET", f"/pipeline/status/{pipeline_id}")
    return result


def print_pipeline_result(result: Dict[str, Any]):
    """Print pipeline execution result."""
    print(f"\n🎯 Pipeline Result:")
    print(f"   Status: {result['status']}")
    print(f"   Pipeline ID: {result.get('pipeline_id', 'N/A')}")
    
    if 'task_id' in result:
        print(f"   Task ID: {result['task_id']}")
    
    if 'total_duration' in result:
        print(f"   Duration: {result['total_duration']:.2f}s")
    
    if 'phases_completed' in result:
        print(f"   Phases Completed: {result['phases_completed']}")
    
    if 'phases_failed' in result:
        print(f"   Phases Failed: {result['phases_failed']}")
    
    if 'failed_phases' in result and result['failed_phases']:
        print(f"   Failed Phases: {', '.join(result['failed_phases'])}")
    
    if 'error' in result:
        print(f"   Error: {result['error']}")
    
    if 'message' in result:
        print(f"   Message: {result['message']}")


def print_components_status(status: Dict[str, Any]):
    """Print components status."""
    print(f"\n🔧 Components Status:")
    components = status.get('components', {})
    
    for component, info in components.items():
        status_icon = "✅" if info.get('available', False) else "❌"
        print(f"   {status_icon} {component.replace('_', ' ').title()}: {info.get('status', 'unknown')}")
        
        if 'info' in info and isinstance(info['info'], dict):
            for key, value in info['info'].items():
                print(f"      {key}: {value}")
    
    overall_status = status.get('overall_status', 'unknown')
    overall_icon = "✅" if overall_status == 'ready' else "❌"
    print(f"\n   {overall_icon} Overall Status: {overall_status}")


def main():
    parser = argparse.ArgumentParser(description="Test AI processing pipeline phases")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create bookmark command
    create_parser = subparsers.add_parser("create", help="Create a Twitter bookmark")
    create_parser.add_argument("tweet_id", help="Twitter tweet ID")
    create_parser.add_argument("--force", action="store_true", help="Force refresh if already exists")
    
    # Test phase command
    test_parser = subparsers.add_parser("test", help="Test a specific phase")
    test_parser.add_argument("content_id", help="Content item ID")
    test_parser.add_argument("phase", choices=["bookmark_caching", "media_analysis", "content_understanding", "categorization"], help="Phase to test")
    test_parser.add_argument("--force", action="store_true", help="Force processing even if already completed")
    
    # Get content command
    get_parser = subparsers.add_parser("get", help="Get content item details")
    get_parser.add_argument("content_id", help="Content item ID")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get sub-phase status")
    status_parser.add_argument("content_id", help="Content item ID")
    
    # Update status command
    update_parser = subparsers.add_parser("update", help="Update sub-phase status")
    update_parser.add_argument("content_id", help="Content item ID")
    update_parser.add_argument("phase", choices=["bookmark_cached", "media_analyzed", "content_understood", "categorized"], help="Phase to update")
    update_parser.add_argument("status", type=bool, help="New status (true/false)")
    update_parser.add_argument("--model", help="Model used for this phase")
    update_parser.add_argument("--results", help="JSON string of results")
    
    # Full workflow command
    workflow_parser = subparsers.add_parser("workflow", help="Run full workflow for a tweet")
    workflow_parser.add_argument("tweet_id", help="Twitter tweet ID")
    workflow_parser.add_argument("--force", action="store_true", help="Force refresh all phases")
    
    # New pipeline commands
    components_parser = subparsers.add_parser("components", help="Test pipeline components")
    
    process_parser = subparsers.add_parser("process", help="Process a bookmark through pipeline")
    process_parser.add_argument("tweet_id", help="Twitter tweet ID")
    process_parser.add_argument("--force", action="store_true", help="Force refresh")
    process_parser.add_argument("--sync", action="store_true", help="Run synchronously")
    process_parser.add_argument("--models", help="JSON string of model overrides")
    
    fetch_parser = subparsers.add_parser("fetch", help="Fetch bookmarks from collection")
    fetch_parser.add_argument("--url", help="Collection URL")
    fetch_parser.add_argument("--max", type=int, default=100, help="Maximum bookmarks to fetch")
    fetch_parser.add_argument("--force", action="store_true", help="Force refresh")
    
    synthesis_parser = subparsers.add_parser("synthesis", help="Generate synthesis documents")
    synthesis_parser.add_argument("--min", type=int, default=3, help="Minimum bookmarks per category")
    synthesis_parser.add_argument("--models", help="JSON string of model overrides")
    
    pipeline_parser = subparsers.add_parser("pipeline", help="Execute seven-phase pipeline")
    pipeline_parser.add_argument("--config", required=True, help="JSON string of pipeline configuration")
    pipeline_parser.add_argument("--models", help="JSON string of model overrides")
    pipeline_parser.add_argument("--sync", action="store_true", help="Run synchronously")
    
    pipeline_status_parser = subparsers.add_parser("pipeline-status", help="Get pipeline status")
    pipeline_status_parser.add_argument("pipeline_id", help="Pipeline execution ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "create":
            result = create_test_bookmark(args.tweet_id, args.force)
            print_content_summary(result)
            
        elif args.command == "test":
            result = test_phase(args.content_id, args.phase, args.force)
            print(f"\n🎯 Test Result: {json.dumps(result, indent=2)}")
            
        elif args.command == "get":
            result = get_content_item(args.content_id)
            print_content_summary(result)
            
        elif args.command == "status":
            result = get_subphase_status(args.content_id)
            print_subphase_status(result)
            
        elif args.command == "update":
            results = json.loads(args.results) if args.results else None
            result = update_subphase_status(args.content_id, args.phase, args.status, args.model, results)
            print_subphase_status(result)
            
        elif args.command == "workflow":
            print(f"🚀 Running full workflow for tweet {args.tweet_id}")
            
            # Step 1: Create bookmark
            content = create_test_bookmark(args.tweet_id, args.force)
            content_id = content['id']
            
            # Step 2: Run all phases in sequence
            phases = ["bookmark_caching", "media_analysis", "content_understanding", "categorization"]
            
            for phase in phases:
                print(f"\n🔄 Running phase: {phase}")
                try:
                    result = test_phase(content_id, phase, args.force)
                    print(f"   ✅ {phase}: {result.get('message', 'Completed')}")
                except Exception as e:
                    print(f"   ❌ {phase}: Failed - {e}")
                    break
            
            # Step 3: Show final status
            print(f"\n📊 Final Status:")
            final_content = get_content_item(content_id)
            print_content_summary(final_content)
            
            final_status = get_subphase_status(content_id)
            print_subphase_status(final_status)
            
        # New pipeline commands
        elif args.command == "components":
            result = test_pipeline_components()
            print_components_status(result)
            
        elif args.command == "process":
            models_override = json.loads(args.models) if args.models else None
            result = process_bookmark(
                tweet_id=args.tweet_id,
                force_refresh=args.force,
                models_override=models_override,
                run_async=not args.sync
            )
            print_pipeline_result(result)
            
        elif args.command == "fetch":
            result = fetch_bookmarks(
                collection_url=args.url,
                max_results=args.max,
                force_refresh=args.force
            )
            print(f"\n📥 Fetch Results:")
            print(f"   Fetched: {result['fetched_count']}")
            print(f"   Skipped: {result['skipped_count']}")
            print(f"   Failed: {result['failed_count']}")
            
            if result['fetched_bookmarks']:
                print(f"\n📄 Sample Fetched Bookmarks:")
                for i, bookmark in enumerate(result['fetched_bookmarks'][:3]):
                    print(f"   {i+1}. {bookmark['tweet_id']} by @{bookmark['author']} ({bookmark['engagement_total']} engagement)")
            
        elif args.command == "synthesis":
            models_override = json.loads(args.models) if args.models else None
            result = generate_synthesis(
                models_override=models_override,
                min_bookmarks=args.min
            )
            print(f"\n📚 Synthesis Results:")
            print(f"   Generated: {result['generated_count']}")
            print(f"   Skipped: {result['skipped_count']}")
            
            if result['generated_syntheses']:
                print(f"\n📖 Generated Syntheses:")
                for synthesis in result['generated_syntheses']:
                    print(f"   • {synthesis['category']}/{synthesis['subcategory']} ({synthesis['source_count']} sources)")
            
        elif args.command == "pipeline":
            config = json.loads(args.config)
            models_override = json.loads(args.models) if args.models else None
            result = execute_seven_phase_pipeline(
                config=config,
                models_override=models_override,
                run_async=not args.sync
            )
            print_pipeline_result(result)
            
        elif args.command == "pipeline-status":
            result = get_pipeline_status(args.pipeline_id)
            print(f"\n📊 Pipeline Status:")
            print(f"   Pipeline ID: {result['pipeline_id']}")
            print(f"   Status: {result['status']}")
            print(f"   Current Phase: {result.get('current_phase', 'N/A')}")
            print(f"   Progress: {result.get('progress', 0)}%")
            print(f"   Phases Completed: {result.get('phases_completed', 0)}/{result.get('phases_total', 7)}")
            
            if result.get('message'):
                print(f"   Message: {result['message']}")
            
            if result.get('estimated_completion'):
                print(f"   ETA: {result['estimated_completion']}")
            
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()