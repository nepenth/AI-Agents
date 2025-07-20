#!/usr/bin/env python3
"""
API Documentation Generator Script

Generate comprehensive documentation for Knowledge Base Agent API endpoints.
"""

import json
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from knowledge_base_agent.web import app
from knowledge_base_agent.api_documentation_generator import generate_api_documentation


def main():
    parser = argparse.ArgumentParser(description='Generate comprehensive API documentation')
    parser.add_argument('--output', '-o', default='api_documentation.json',
                       help='Output file for documentation (default: api_documentation.json)')
    parser.add_argument('--format', choices=['json', 'markdown', 'html'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--include-validation', help='Include validation results from file')
    parser.add_argument('--category', help='Generate docs for specific category only')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    print("📚 Generating comprehensive API documentation...")
    print()
    
    try:
        # Load validation results if provided
        validation_results = None
        if args.include_validation:
            with open(args.include_validation, 'r') as f:
                validation_results = json.load(f)
            print(f"📊 Loaded validation results from: {args.include_validation}")
        
        # Generate documentation
        with app.app_context():
            documentation = generate_api_documentation(app, validation_results)
        
        # Filter by category if specified
        if args.category:
            if args.category in documentation['categories']:
                filtered_docs = {
                    'metadata': documentation['metadata'],
                    'statistics': {'total_endpoints': len(documentation['categories'][args.category])},
                    'categories': {args.category: documentation['categories'][args.category]},
                    'endpoints': [ep for ep in documentation['endpoints'] if ep['category'] == args.category]
                }
                documentation = filtered_docs
            else:
                print(f"❌ Category '{args.category}' not found")
                print(f"Available categories: {', '.join(documentation['categories'].keys())}")
                sys.exit(1)
        
        # Display summary
        display_summary(documentation, args)
        
        # Save documentation
        if args.format == 'json':
            save_json_documentation(documentation, args.output)
        elif args.format == 'markdown':
            save_markdown_documentation(documentation, args.output)
        elif args.format == 'html':
            save_html_documentation(documentation, args.output)
        
        print(f"\n💾 Documentation saved to: {args.output}")
        
    except Exception as e:
        print(f"❌ Documentation generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_summary(documentation, args):
    """Display documentation summary."""
    stats = documentation['statistics']
    
    print("📊 DOCUMENTATION SUMMARY")
    print("=" * 50)
    print(f"Total Endpoints Documented: {stats['total_endpoints']}")
    print()
    
    print("📂 BY CATEGORY")
    print("-" * 30)
    for category, count in stats['by_category'].items():
        print(f"  {category}: {count}")
    print()
    
    if 'by_version' in stats:
        print("🔢 BY VERSION")
        print("-" * 20)
        for version, count in stats['by_version'].items():
            print(f"  {version}: {count}")
        print()
    
    if 'by_method' in stats:
        print("🌐 BY HTTP METHOD")
        print("-" * 20)
        for method, count in stats['by_method'].items():
            print(f"  {method}: {count}")
        print()
    
    if not args.summary:
        print("📋 ENDPOINT CATEGORIES")
        print("-" * 30)
        for category, endpoints in documentation['categories'].items():
            print(f"\n📂 {category} ({len(endpoints)} endpoints)")
            for endpoint in endpoints[:3]:  # Show first 3
                methods = ', '.join(endpoint['methods'])
                print(f"  • {methods} {endpoint['path']}")
                print(f"    {endpoint['summary']}")
            if len(endpoints) > 3:
                print(f"  ... and {len(endpoints) - 3} more")


def save_json_documentation(documentation, output_file):
    """Save documentation as JSON."""
    with open(output_file, 'w') as f:
        json.dump(documentation, f, indent=2, default=str)


def save_markdown_documentation(documentation, output_file):
    """Save documentation as Markdown."""
    md_content = generate_markdown_documentation(documentation)
    with open(output_file, 'w') as f:
        f.write(md_content)


def generate_markdown_documentation(documentation):
    """Generate Markdown documentation."""
    md = []
    
    # Header
    md.append("# Knowledge Base Agent API Documentation")
    md.append("")
    md.append("Comprehensive documentation for all API endpoints.")
    md.append("")
    
    # Statistics
    stats = documentation['statistics']
    md.append("## Overview")
    md.append("")
    md.append(f"- **Total Endpoints:** {stats['total_endpoints']}")
    md.append(f"- **Categories:** {len(stats['by_category'])}")
    if 'by_version' in stats:
        md.append(f"- **API Versions:** {', '.join(stats['by_version'].keys())}")
    md.append("")
    
    # Table of Contents
    md.append("## Table of Contents")
    md.append("")
    for category in documentation['categories'].keys():
        anchor = category.lower().replace(' ', '-').replace('(', '').replace(')', '')
        md.append(f"- [{category}](#{anchor})")
    md.append("")
    
    # Categories
    for category, endpoints in documentation['categories'].items():
        anchor = category.lower().replace(' ', '-').replace('(', '').replace(')', '')
        md.append(f"## {category}")
        md.append("")
        
        for endpoint in endpoints:
            # Endpoint header
            methods = ', '.join(endpoint['methods'])
            md.append(f"### {methods} {endpoint['path']}")
            md.append("")
            
            # Summary and description
            md.append(f"**Summary:** {endpoint['summary']}")
            md.append("")
            if endpoint['description'] != endpoint['summary']:
                md.append(f"**Description:** {endpoint['description']}")
                md.append("")
            
            # Parameters
            if endpoint['path_parameters']:
                md.append("**Path Parameters:**")
                md.append("")
                for param in endpoint['path_parameters']:
                    required = "Required" if param['required'] else "Optional"
                    md.append(f"- `{param['name']}` ({param['type']}, {required}): {param.get('description', 'No description')}")
                md.append("")
            
            if endpoint['query_parameters']:
                md.append("**Query Parameters:**")
                md.append("")
                for param in endpoint['query_parameters']:
                    required = "Required" if param['required'] else "Optional"
                    md.append(f"- `{param['name']}` ({param['type']}, {required}): {param.get('description', 'No description')}")
                md.append("")
            
            # Request body
            if endpoint['request_body']:
                md.append("**Request Body:**")
                md.append("")
                md.append("```json")
                md.append(json.dumps(endpoint['request_body'], indent=2))
                md.append("```")
                md.append("")
            
            # Responses
            if endpoint['responses']:
                md.append("**Responses:**")
                md.append("")
                for response in endpoint['responses']:
                    md.append(f"- **{response['status_code']}**: {response['description']}")
                    if response.get('example'):
                        md.append("  ```json")
                        md.append("  " + json.dumps(response['example'], indent=2).replace('\n', '\n  '))
                        md.append("  ```")
                md.append("")
            
            # Examples
            if endpoint['curl_examples']:
                md.append("**Example (curl):**")
                md.append("")
                md.append("```bash")
                md.append(endpoint['curl_examples'][0])
                md.append("```")
                md.append("")
            
            # Workflow context
            if endpoint['workflow_context']:
                md.append(f"**Workflow Context:** {endpoint['workflow_context']}")
                md.append("")
            
            # Error scenarios
            if endpoint['error_scenarios']:
                md.append("**Common Error Scenarios:**")
                md.append("")
                for scenario in endpoint['error_scenarios']:
                    md.append(f"- {scenario}")
                md.append("")
            
            md.append("---")
            md.append("")
    
    return '\n'.join(md)


def save_html_documentation(documentation, output_file):
    """Save documentation as HTML."""
    html_content = generate_html_documentation(documentation)
    with open(output_file, 'w') as f:
        f.write(html_content)


def generate_html_documentation(documentation):
    """Generate HTML documentation."""
    html = []
    
    # HTML header
    html.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Knowledge Base Agent API Documentation</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1, h2, h3 { color: #333; }
        .endpoint { border: 1px solid #ddd; border-radius: 8px; margin: 20px 0; padding: 20px; }
        .method { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-right: 10px; }
        .get { background: #61affe; color: white; }
        .post { background: #49cc90; color: white; }
        .put { background: #fca130; color: white; }
        .delete { background: #f93e3e; color: white; }
        .patch { background: #50e3c2; color: white; }
        pre { background: #f5f5f5; padding: 15px; border-radius: 4px; overflow-x: auto; }
        .toc { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .category { margin: 30px 0; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat { background: #e9ecef; padding: 15px; border-radius: 8px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Knowledge Base Agent API Documentation</h1>
        <p>Comprehensive documentation for all API endpoints.</p>
""")
    
    # Statistics
    stats = documentation['statistics']
    html.append('<div class="stats">')
    html.append(f'<div class="stat"><strong>{stats["total_endpoints"]}</strong><br>Total Endpoints</div>')
    html.append(f'<div class="stat"><strong>{len(stats["by_category"])}</strong><br>Categories</div>')
    if 'by_version' in stats:
        html.append(f'<div class="stat"><strong>{len(stats["by_version"])}</strong><br>API Versions</div>')
    html.append('</div>')
    
    # Table of Contents
    html.append('<div class="toc">')
    html.append('<h2>Table of Contents</h2>')
    html.append('<ul>')
    for category in documentation['categories'].keys():
        anchor = category.lower().replace(' ', '-').replace('(', '').replace(')', '')
        html.append(f'<li><a href="#{anchor}">{category}</a></li>')
    html.append('</ul>')
    html.append('</div>')
    
    # Categories
    for category, endpoints in documentation['categories'].items():
        anchor = category.lower().replace(' ', '-').replace('(', '').replace(')', '')
        html.append(f'<div class="category" id="{anchor}">')
        html.append(f'<h2>{category}</h2>')
        
        for endpoint in endpoints:
            html.append('<div class="endpoint">')
            
            # Methods and path
            methods_html = []
            for method in endpoint['methods']:
                methods_html.append(f'<span class="method {method.lower()}">{method}</span>')
            html.append(f'<h3>{"".join(methods_html)}{endpoint["path"]}</h3>')
            
            # Summary
            html.append(f'<p><strong>Summary:</strong> {endpoint["summary"]}</p>')
            
            # Description
            if endpoint['description'] != endpoint['summary']:
                html.append(f'<p><strong>Description:</strong> {endpoint["description"]}</p>')
            
            # Parameters
            if endpoint['path_parameters']:
                html.append('<h4>Path Parameters</h4>')
                html.append('<ul>')
                for param in endpoint['path_parameters']:
                    required = "Required" if param['required'] else "Optional"
                    html.append(f'<li><code>{param["name"]}</code> ({param["type"]}, {required}): {param.get("description", "No description")}</li>')
                html.append('</ul>')
            
            # Request body
            if endpoint['request_body']:
                html.append('<h4>Request Body</h4>')
                html.append('<pre><code>' + json.dumps(endpoint['request_body'], indent=2) + '</code></pre>')
            
            # Example
            if endpoint['curl_examples']:
                html.append('<h4>Example</h4>')
                html.append('<pre><code>' + endpoint['curl_examples'][0] + '</code></pre>')
            
            html.append('</div>')
        
        html.append('</div>')
    
    # HTML footer
    html.append("""
    </div>
</body>
</html>""")
    
    return '\n'.join(html)


if __name__ == "__main__":
    main()