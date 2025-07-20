#!/usr/bin/env python3
"""
API Validation CLI Script

Run comprehensive validation of Knowledge Base Agent API endpoints.
"""

import json
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from knowledge_base_agent.web import app
from knowledge_base_agent.api_validator import run_api_validation
from knowledge_base_agent.api_functionality_validator import run_functionality_validation


def main():
    parser = argparse.ArgumentParser(description='Validate Knowledge Base Agent API endpoints')
    parser.add_argument('--base-url', default='http://localhost:5000', 
                       help='Base URL for API testing (default: http://localhost:5000)')
    parser.add_argument('--output', '-o', help='Output file for results (JSON format)')
    parser.add_argument('--summary-only', action='store_true', 
                       help='Show only summary information')
    parser.add_argument('--errors-only', action='store_true',
                       help='Show only errors and warnings')
    parser.add_argument('--functionality', action='store_true',
                       help='Run detailed functionality tests (requires server running)')
    parser.add_argument('--skip-server-tests', action='store_true',
                       help='Skip tests that require server to be running')
    
    args = parser.parse_args()
    
    print("🔍 Starting API endpoint validation...")
    print(f"📡 Testing against: {args.base_url}")
    print()
    
    try:
        with app.app_context():
            results = run_api_validation(app, args.base_url if not args.skip_server_tests else None)
            
            # Run functionality tests if requested
            if args.functionality and not args.skip_server_tests:
                print("🔧 Running detailed functionality tests...")
                functionality_results = run_functionality_validation(results['endpoints'], args.base_url)
                results['functionality'] = functionality_results
                print(f"✅ Functionality tests completed. Pass rate: {functionality_results['statistics']['pass_rate']:.1f}%")
                print()
            
        # Display results
        display_results(results, args)
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")
            
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)


def display_results(results, args):
    """Display validation results in a formatted way."""
    stats = results['statistics']
    summary = results['summary']
    
    # Always show summary
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Total Endpoints: {summary['total_endpoints']}")
    print(f"Total HTTP Methods: {summary['total_methods']}")
    print(f"Deprecated Endpoints: {summary['deprecated_endpoints']}")
    print()
    
    print("📂 ENDPOINTS BY CATEGORY")
    print("-" * 30)
    for category, count in summary['categories'].items():
        print(f"  {category}: {count}")
    print()
    
    print("🧪 VALIDATION RESULTS")
    print("-" * 30)
    print(f"✅ Successful: {stats['successes']}")
    print(f"⚠️  Warnings: {stats['warnings']}")
    print(f"❌ Errors: {stats['errors']}")
    print(f"📋 Total Tests: {stats['total_validations']}")
    print()
    
    if args.summary_only:
        return
    
    # Show detailed results
    validations = results['validations']
    
    # Show errors first
    errors = [r for r in validations['accessibility'] + validations['response_formats'] 
              if r['status'] == 'error']
    
    if errors:
        print("❌ ERRORS FOUND")
        print("-" * 20)
        for error in errors:
            print(f"  {error['method']} {error['endpoint']}")
            print(f"    {error['message']}")
            if error.get('error_details'):
                print(f"    Details: {error['error_details']}")
        print()
    
    # Show warnings
    warnings = [r for r in validations['route_conflicts'] + validations['accessibility'] + validations['response_formats']
                if r['status'] == 'warning']
    
    if warnings:
        print("⚠️  WARNINGS FOUND")
        print("-" * 20)
        for warning in warnings:
            print(f"  {warning['method']} {warning['endpoint']}")
            print(f"    {warning['message']}")
        print()
    
    if args.errors_only:
        return
    
    # Show endpoint details
    print("📋 ENDPOINT DETAILS")
    print("-" * 20)
    
    for category, endpoints in summary['by_category'].items():
        print(f"\n📂 {category}")
        for endpoint in endpoints:
            status_icon = "🚫" if endpoint['is_deprecated'] else "✅"
            methods_str = ", ".join(endpoint['methods'])
            print(f"  {status_icon} {methods_str} {endpoint['rule']}")
            if endpoint['docstring']:
                # Show first line of docstring
                first_line = endpoint['docstring'].split('\n')[0].strip()
                if first_line:
                    print(f"      {first_line}")


if __name__ == "__main__":
    main()