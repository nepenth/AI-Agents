#!/usr/bin/env python3
"""
SocketIO Event Analysis Script

Analyze SocketIO events and generate comprehensive documentation.
"""

import json
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from knowledge_base_agent.web import app, socketio
from knowledge_base_agent.socketio_analyzer import analyze_socketio_events


def main():
    parser = argparse.ArgumentParser(description='Analyze SocketIO events')
    parser.add_argument('--output', '-o', default='socketio_analysis.json',
                       help='Output file for analysis results (default: socketio_analysis.json)')
    parser.add_argument('--format', choices=['json', 'markdown'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--category', help='Analyze specific category only')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    print("🔌 Analyzing SocketIO events...")
    print()
    
    try:
        with app.app_context():
            analysis = analyze_socketio_events(app, socketio)
        
        # Filter by category if specified
        if args.category:
            if args.category in analysis['categories']:
                filtered_analysis = {
                    'metadata': analysis['metadata'],
                    'statistics': {'by_category': {args.category: len(analysis['categories'][args.category])}},
                    'categories': {args.category: analysis['categories'][args.category]},
                    'events': [e for e in analysis['events'] if e in analysis['categories'][args.category]]
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
        print(f"❌ SocketIO analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def display_summary(analysis, args):
    """Display analysis summary."""
    metadata = analysis['metadata']
    stats = analysis['statistics']
    
    print("📊 SOCKETIO EVENT ANALYSIS SUMMARY")
    print("=" * 50)
    print(f"Total Events: {metadata['total_events']}")
    print(f"Incoming Events: {metadata['incoming_events']}")
    print(f"Outgoing Events: {metadata['outgoing_events']}")
    print(f"Bidirectional Events: {metadata['bidirectional_events']}")
    print()
    
    print("📂 EVENTS BY CATEGORY")
    print("-" * 30)
    for category, count in stats['by_category'].items():
        print(f"  {category}: {count}")
    print()
    
    print("🔄 EVENTS BY DIRECTION")
    print("-" * 25)
    for direction, count in stats['by_direction'].items():
        print(f"  {direction}: {count}")
    print()
    
    if not args.summary:
        print("📋 EVENT DETAILS")
        print("-" * 20)
        
        for category, events in analysis['categories'].items():
            if events:  # Only show categories with events
                print(f"\n📂 {category} ({len(events)} events)")
                for event in events[:3]:  # Show first 3
                    direction_icon = "📥" if event['direction'] == 'incoming' else "📤"
                    print(f"  {direction_icon} {event['name']}")
                    print(f"    {event['description']}")
                    if event['parameters']:
                        param_count = len(event['parameters'])
                        print(f"    Parameters: {param_count}")
                if len(events) > 3:
                    print(f"  ... and {len(events) - 3} more")


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
    md.append("# SocketIO Event Analysis")
    md.append("")
    md.append("Comprehensive analysis of SocketIO real-time communication events.")
    md.append("")
    
    # Statistics
    metadata = analysis['metadata']
    stats = analysis['statistics']
    
    md.append("## Overview")
    md.append("")
    md.append(f"- **Total Events:** {metadata['total_events']}")
    md.append(f"- **Incoming Events:** {metadata['incoming_events']}")
    md.append(f"- **Outgoing Events:** {metadata['outgoing_events']}")
    md.append(f"- **Bidirectional Events:** {metadata['bidirectional_events']}")
    md.append("")
    
    # Event patterns
    if 'event_patterns' in analysis:
        md.append("## Event Patterns")
        md.append("")
        for pattern, events in analysis['event_patterns'].items():
            md.append(f"### {pattern}")
            md.append("")
            for event in events:
                md.append(f"- `{event}`")
            md.append("")
    
    # Categories
    for category, events in analysis['categories'].items():
        if events:  # Only show categories with events
            md.append(f"## {category}")
            md.append("")
            
            for event in events:
                direction_icon = "📥" if event['direction'] == 'incoming' else "📤"
                md.append(f"### {direction_icon} {event['name']}")
                md.append("")
                md.append(f"**Direction:** {event['direction'].title()}")
                md.append("")
                md.append(f"**Description:** {event['description']}")
                md.append("")
                
                # Parameters
                if event['parameters']:
                    md.append("**Parameters:**")
                    md.append("")
                    md.append("| Name | Type | Required | Description |")
                    md.append("|------|------|----------|-------------|")
                    
                    for param in event['parameters']:
                        required = "Yes" if param['required'] else "No"
                        desc = param['description'] or ""
                        md.append(f"| `{param['name']}` | {param['type']} | {required} | {desc} |")
                    
                    md.append("")
                
                # Example data
                if event['example_data']:
                    md.append("**Example Data:**")
                    md.append("")
                    md.append("```json")
                    md.append(json.dumps(event['example_data'], indent=2))
                    md.append("```")
                    md.append("")
                
                # Handler function
                if event['handler_function']:
                    md.append(f"**Handler Function:** `{event['handler_function']}`")
                    md.append("")
                
                # Emitter locations
                if event['emitter_locations']:
                    md.append(f"**Emitted From:** {', '.join(event['emitter_locations'])}")
                    md.append("")
                
                md.append("---")
                md.append("")
    
    return '\n'.join(md)


if __name__ == "__main__":
    main()