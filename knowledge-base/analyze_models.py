#!/usr/bin/env python3
"""
Database Model Analysis Script

Analyze SQLAlchemy models and generate comprehensive documentation.
"""

import json
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from knowledge_base_agent.web import app
from knowledge_base_agent.models import db
from knowledge_base_agent.model_analyzer import analyze_database_models


def main():
    parser = argparse.ArgumentParser(description='Analyze database models')
    parser.add_argument('--output', '-o', default='model_analysis.json',
                       help='Output file for analysis results (default: model_analysis.json)')
    parser.add_argument('--format', choices=['json', 'markdown'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--category', help='Analyze specific category only')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    print("🗄️  Analyzing database models...")
    print()
    
    try:
        with app.app_context():
            analysis = analyze_database_models(db)
        
        # Filter by category if specified
        if args.category:
            if args.category in analysis['categories']:
                filtered_analysis = {
                    'metadata': analysis['metadata'],
                    'statistics': {'models_by_category': {args.category: len(analysis['categories'][args.category])}},
                    'categories': {args.category: analysis['categories'][args.category]},
                    'models': [m for m in analysis['models'] if m['name'] in [model['name'] for model in analysis['categories'][args.category]]]
                }
                analysis = filtered_analysis
            else:
                print(f"❌ Category '{args.category}' not found")
                print(f"Available categories: {', '.join(analysis['categories'].keys())}")
                sys.exit(1)
        
        # Display summary
        display_summary(analysis, args)
        
        # Save analysis
        if args.format == 'json':
            save_json_analysis(analysis, args.output)
        elif args.format == 'markdown':
            save_markdown_analysis(analysis, args.output)
        
        print(f"\n💾 Analysis saved to: {args.output}")
        
    except Exception as e:
        print(f"❌ Model analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_summary(analysis, args):
    """Display analysis summary."""
    metadata = analysis['metadata']
    stats = analysis['statistics']
    
    print("📊 MODEL ANALYSIS SUMMARY")
    print("=" * 50)
    print(f"Total Models: {metadata['total_models']}")
    print(f"Total Fields: {metadata['total_fields']}")
    print(f"Total Relationships: {metadata['total_relationships']}")
    print(f"Total Constraints: {metadata['total_constraints']}")
    print()
    
    print("📂 MODELS BY CATEGORY")
    print("-" * 30)
    for category, count in stats['models_by_category'].items():
        print(f"  {category}: {count}")
    print()
    
    if 'field_types' in stats:
        print("🏷️  FIELD TYPES")
        print("-" * 20)
        for field_type, count in stats['field_types'].items():
            print(f"  {field_type}: {count}")
        print()
    
    if 'relationship_types' in stats:
        print("🔗 RELATIONSHIP TYPES")
        print("-" * 25)
        for rel_type, count in stats['relationship_types'].items():
            print(f"  {rel_type}: {count}")
        print()
    
    if not args.summary:
        print("📋 MODEL DETAILS")
        print("-" * 20)
        
        for category, models in analysis['categories'].items():
            print(f"\n📂 {category} ({len(models)} models)")
            for model in models[:3]:  # Show first 3
                print(f"  • {model['name']} ({model['table_name']})")
                print(f"    {model['purpose']}")
                print(f"    Fields: {len(model['fields'])}, Relationships: {len(model['relationships'])}")
            if len(models) > 3:
                print(f"  ... and {len(models) - 3} more")


def save_json_analysis(analysis, output_file):
    """Save analysis as JSON."""
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2, default=str)


def save_markdown_analysis(analysis, output_file):
    """Save analysis as Markdown."""
    md_content = generate_markdown_analysis(analysis)
    with open(output_file, 'w') as f:
        f.write(md_content)


def generate_markdown_analysis(analysis):
    """Generate Markdown analysis."""
    md = []
    
    # Header
    md.append("# Database Model Analysis")
    md.append("")
    md.append("Comprehensive analysis of SQLAlchemy database models.")
    md.append("")
    
    # Statistics
    metadata = analysis['metadata']
    stats = analysis['statistics']
    
    md.append("## Overview")
    md.append("")
    md.append(f"- **Total Models:** {metadata['total_models']}")
    md.append(f"- **Total Fields:** {metadata['total_fields']}")
    md.append(f"- **Total Relationships:** {metadata['total_relationships']}")
    md.append(f"- **Total Constraints:** {metadata['total_constraints']}")
    md.append("")
    
    # Field types
    if 'field_types' in stats:
        md.append("### Field Type Distribution")
        md.append("")
        for field_type, count in stats['field_types'].items():
            md.append(f"- **{field_type}:** {count}")
        md.append("")
    
    # Categories
    for category, models in analysis['categories'].items():
        md.append(f"## {category}")
        md.append("")
        
        for model in models:
            md.append(f"### {model['name']}")
            md.append("")
            md.append(f"**Table:** `{model['table_name']}`")
            md.append("")
            md.append(f"**Purpose:** {model['purpose']}")
            md.append("")
            
            # Fields
            if model['fields']:
                md.append("**Fields:**")
                md.append("")
                md.append("| Name | Type | Nullable | Primary Key | Unique | Description |")
                md.append("|------|------|----------|-------------|--------|-------------|")
                
                for field in model['fields']:
                    nullable = "Yes" if field['nullable'] else "No"
                    pk = "Yes" if field['primary_key'] else "No"
                    unique = "Yes" if field['unique'] else "No"
                    desc = field['description'] or ""
                    
                    md.append(f"| `{field['name']}` | {field['type']} | {nullable} | {pk} | {unique} | {desc} |")
                
                md.append("")
            
            # Relationships
            if model['relationships']:
                md.append("**Relationships:**")
                md.append("")
                for rel in model['relationships']:
                    md.append(f"- `{rel['name']}` → {rel['target_model']} ({rel['relationship_type']})")
                md.append("")
            
            # Business rules
            if model['business_rules']:
                md.append("**Business Rules:**")
                md.append("")
                for rule in model['business_rules']:
                    md.append(f"- {rule}")
                md.append("")
            
            # Common queries
            if model['common_queries']:
                md.append("**Common Queries:**")
                md.append("")
                md.append("```python")
                for query in model['common_queries'][:3]:  # Show first 3
                    md.append(query)
                md.append("```")
                md.append("")
            
            md.append("---")
            md.append("")
    
    return '\n'.join(md)


if __name__ == "__main__":
    main()