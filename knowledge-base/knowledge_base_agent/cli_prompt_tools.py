#!/usr/bin/env python3
"""
CLI Tools for JSON Prompt Validation and Management

This module provides command-line tools for validating JSON prompt configurations,
testing prompt rendering, comparing outputs, and managing the prompt system.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

# Add the knowledge_base_agent directory to the path
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_base_agent.json_prompt_manager import JsonPromptManager, JsonPromptManagerError
from knowledge_base_agent.json_prompt import JsonPrompt, JsonPromptError
from knowledge_base_agent.test_prompt_comparison import PromptComparisonTester
from knowledge_base_agent.test_integration import IntegrationTester
from knowledge_base_agent.test_performance_quality import PerformanceQualityTester
from knowledge_base_agent.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class PromptCLITools:
    """Command-line interface tools for JSON prompt management."""
    
    def __init__(self):
        """Initialize CLI tools."""
        self.config = Config.from_env()
        self.manager = JsonPromptManager(self.config)
    
    def validate_prompt(self, prompt_id: str, model_type: str = "standard") -> Dict[str, Any]:
        """Validate a specific prompt."""
        print(f"🔍 Validating prompt: {prompt_id} ({model_type})")
        
        try:
            # Load and validate prompt
            validation_result = self.manager.validate_prompt(prompt_id, model_type)
            
            if validation_result['valid']:
                print(f"✅ {prompt_id}: VALID")
                
                if validation_result['examples_valid']:
                    print(f"   ✅ Examples: All examples render successfully")
                else:
                    print(f"   ⚠️  Examples: Some examples failed to render")
                
                print(f"   📊 Schema: {'✅ Valid' if validation_result['schema_valid'] else '❌ Invalid'}")
                
            else:
                print(f"❌ {prompt_id}: INVALID")
                for error in validation_result['errors']:
                    print(f"   ❌ {error}")
            
            return validation_result
            
        except Exception as e:
            print(f"❌ {prompt_id}: VALIDATION FAILED - {e}")
            return {'valid': False, 'errors': [str(e)]}
    
    def validate_all_prompts(self) -> Dict[str, Any]:
        """Validate all available prompts."""
        print("🔍 Validating all prompts...")
        
        available = self.manager.get_available_prompts()
        results = {}
        total_prompts = 0
        valid_prompts = 0
        
        for model_type, prompt_ids in available.items():
            for prompt_id in prompt_ids:
                total_prompts += 1
                result = self.validate_prompt(prompt_id, model_type)
                results[f"{model_type}:{prompt_id}"] = result
                
                if result['valid']:
                    valid_prompts += 1
        
        print(f"\n📊 Validation Summary:")
        print(f"   Total Prompts: {total_prompts}")
        print(f"   ✅ Valid: {valid_prompts}")
        print(f"   ❌ Invalid: {total_prompts - valid_prompts}")
        print(f"   📈 Success Rate: {(valid_prompts / total_prompts) * 100:.1f}%")
        
        return {
            'total_prompts': total_prompts,
            'valid_prompts': valid_prompts,
            'success_rate': (valid_prompts / total_prompts) * 100,
            'results': results
        }
    
    def test_prompt_rendering(self, prompt_id: str, parameters: Dict[str, Any], 
                            model_type: str = "standard", variant: Optional[str] = None) -> Dict[str, Any]:
        """Test prompt rendering with given parameters."""
        print(f"🎨 Testing prompt rendering: {prompt_id} ({model_type})")
        
        try:
            # Render prompt
            result = self.manager.render_prompt(prompt_id, parameters, model_type, variant)
            
            print(f"✅ Rendering successful:")
            print(f"   📏 Content Length: {len(result.content)} characters")
            print(f"   ⏱️  Render Time: {result.render_time_ms:.2f}ms")
            print(f"   🔧 Parameters Used: {len(result.parameters_used)}")
            
            if result.warnings:
                print(f"   ⚠️  Warnings: {len(result.warnings)}")
                for warning in result.warnings:
                    print(f"      - {warning}")
            
            # Show content preview
            content_preview = result.content[:200] + "..." if len(result.content) > 200 else result.content
            print(f"   📄 Content Preview: {content_preview}")
            
            return {
                'success': True,
                'content_length': len(result.content),
                'render_time_ms': result.render_time_ms,
                'parameters_used': result.parameters_used,
                'warnings': result.warnings
            }
            
        except Exception as e:
            print(f"❌ Rendering failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def compare_prompts(self, test_name: Optional[str] = None) -> Dict[str, Any]:
        """Compare original vs JSON prompt outputs."""
        print("🔄 Comparing original vs JSON prompt outputs...")
        
        try:
            tester = PromptComparisonTester(self.config)
            
            if test_name:
                # Run specific test
                test_case = None
                for tc in tester.test_cases:
                    if tc.name == test_name:
                        test_case = tc
                        break
                
                if not test_case:
                    print(f"❌ Test '{test_name}' not found")
                    available_tests = [tc.name for tc in tester.test_cases]
                    print(f"Available tests: {available_tests}")
                    return {'success': False, 'error': 'Test not found'}
                
                result = tester.run_comparison_test(test_case)
                
                if result.error:
                    print(f"❌ {result.test_name}: {result.error}")
                    return {'success': False, 'error': result.error}
                elif result.identical:
                    print(f"✅ {result.test_name}: IDENTICAL")
                else:
                    status = "🔶 HIGH SIMILARITY" if result.similarity_score >= 0.95 else "⚠️ LOW SIMILARITY"
                    print(f"{status} {result.test_name}: {result.similarity_score:.1%}")
                
                return {
                    'success': True,
                    'test_name': result.test_name,
                    'identical': result.identical,
                    'similarity_score': result.similarity_score,
                    'differences_count': len(result.differences)
                }
            
            else:
                # Run all tests
                summary = tester.run_all_tests()
                
                print(f"\n📊 Comparison Summary:")
                print(f"   Total Tests: {summary['total_tests']}")
                print(f"   ✅ Identical: {summary['identical']}")
                print(f"   🔶 High Similarity: {summary['high_similarity']}")
                print(f"   ❌ Failed: {summary['failed']}")
                print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
                
                return summary
                
        except Exception as e:
            print(f"❌ Comparison failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_prompts(self, model_type: Optional[str] = None, category: Optional[str] = None) -> Dict[str, Any]:
        """List available prompts with filtering options."""
        print("📋 Listing available prompts...")
        
        try:
            available = self.manager.get_available_prompts()
            
            # Filter by model type if specified
            if model_type:
                if model_type not in available:
                    print(f"❌ Model type '{model_type}' not found")
                    return {'success': False, 'error': 'Model type not found'}
                available = {model_type: available[model_type]}
            
            # Filter by category if specified
            if category:
                filtered_available = {}
                for mt, prompt_ids in available.items():
                    filtered_prompts = []
                    for prompt_id in prompt_ids:
                        try:
                            info = self.manager.get_prompt_info(prompt_id, mt)
                            if info.get('category') == category:
                                filtered_prompts.append(prompt_id)
                        except:
                            continue
                    if filtered_prompts:
                        filtered_available[mt] = filtered_prompts
                available = filtered_available
            
            # Display results
            total_prompts = 0
            for model_type, prompt_ids in available.items():
                print(f"\n📁 {model_type.upper()} Prompts ({len(prompt_ids)}):")
                for prompt_id in sorted(prompt_ids):
                    try:
                        info = self.manager.get_prompt_info(prompt_id, model_type)
                        print(f"   📄 {prompt_id}")
                        print(f"      Name: {info.get('prompt_name', 'N/A')}")
                        print(f"      Category: {info.get('category', 'N/A')}")
                        print(f"      Description: {info.get('description', 'N/A')[:80]}...")
                        total_prompts += 1
                    except Exception as e:
                        print(f"   ❌ {prompt_id}: Error loading info - {e}")
            
            print(f"\n📊 Total Prompts: {total_prompts}")
            
            return {
                'success': True,
                'total_prompts': total_prompts,
                'prompts_by_type': available
            }
            
        except Exception as e:
            print(f"❌ Listing failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_prompt_info(self, prompt_id: str, model_type: str = "standard") -> Dict[str, Any]:
        """Get detailed information about a specific prompt."""
        print(f"ℹ️  Getting prompt information: {prompt_id} ({model_type})")
        
        try:
            info = self.manager.get_prompt_info(prompt_id, model_type)
            
            print(f"📄 Prompt: {info['prompt_name']}")
            print(f"   ID: {info['prompt_id']}")
            print(f"   Model Type: {info['model_type']}")
            print(f"   Category: {info['category']}")
            print(f"   Task: {info['task']}")
            print(f"   Description: {info['description']}")
            
            print(f"\n🔧 Parameters:")
            print(f"   Required: {info['required_parameters']}")
            print(f"   Optional: {info['optional_parameters']}")
            
            if info['variants']:
                print(f"\n🔄 Variants: {info['variants']}")
            
            if info['examples']:
                print(f"\n📚 Examples: {len(info['examples'])}")
                for i, example in enumerate(info['examples']):
                    print(f"   {i+1}. {example['name']}: {example.get('notes', 'No description')}")
            
            metadata = info.get('metadata', {})
            if metadata:
                print(f"\n📊 Metadata:")
                print(f"   Version: {metadata.get('version', 'N/A')}")
                print(f"   Quality Score: {metadata.get('quality_score', 'N/A')}")
                print(f"   Tags: {metadata.get('tags', [])}")
            
            return {'success': True, 'info': info}
            
        except Exception as e:
            print(f"❌ Failed to get prompt info: {e}")
            return {'success': False, 'error': str(e)}
    
    def export_catalog(self, output_file: Path) -> Dict[str, Any]:
        """Export a complete catalog of all prompts."""
        print(f"📤 Exporting prompt catalog to: {output_file}")
        
        try:
            catalog = self.manager.export_prompt_catalog(output_file)
            
            print(f"✅ Catalog exported successfully:")
            print(f"   📄 Total Prompts: {catalog['total_prompts']}")
            print(f"   📁 Model Types: {list(catalog['model_types'].keys())}")
            print(f"   🏷️  Categories: {list(catalog['categories'].keys())}")
            print(f"   📅 Generated: {catalog['generated_at']}")
            
            return {'success': True, 'catalog': catalog}
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests."""
        print("🧪 Running integration tests...")
        
        try:
            tester = IntegrationTester()
            summary = tester.run_all_integration_tests()
            
            print(f"\n📊 Integration Test Results:")
            print(f"   Total Tests: {summary['total_tests']}")
            print(f"   ✅ Passed: {summary['passed']}")
            print(f"   ❌ Failed: {summary['failed']}")
            print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
            
            return summary
            
        except Exception as e:
            print(f"❌ Integration tests failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance and quality tests."""
        print("⚡ Running performance and quality tests...")
        
        try:
            tester = PerformanceQualityTester(self.config)
            summary = tester.run_comprehensive_tests()
            
            print(f"\n📊 Performance & Quality Results:")
            print(f"   Performance Success Rate: {summary['performance']['success_rate']:.1f}%")
            print(f"   Quality Average Score: {summary['quality']['avg_quality_score']:.1f}/10")
            print(f"   Overall Success: {'✅ PASSED' if summary['overall_success'] else '❌ FAILED'}")
            
            return summary
            
        except Exception as e:
            print(f"❌ Performance tests failed: {e}")
            return {'success': False, 'error': str(e)}


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="JSON Prompt System CLI Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate --all                           # Validate all prompts
  %(prog)s validate --prompt categorization_standard # Validate specific prompt
  %(prog)s test --prompt chat_standard               # Test prompt rendering
  %(prog)s list --category chat                     # List prompts by category
  %(prog)s info --prompt kb_item_generation_standard # Get prompt details
  %(prog)s compare --test categorization_single_tweet # Compare specific test
  %(prog)s export --output catalog.json             # Export prompt catalog
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate prompts')
    validate_group = validate_parser.add_mutually_exclusive_group(required=True)
    validate_group.add_argument('--all', action='store_true', help='Validate all prompts')
    validate_group.add_argument('--prompt', help='Validate specific prompt')
    validate_parser.add_argument('--model-type', default='standard', choices=['standard', 'reasoning'], help='Model type')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test prompt rendering')
    test_parser.add_argument('--prompt', required=True, help='Prompt ID to test')
    test_parser.add_argument('--model-type', default='standard', choices=['standard', 'reasoning'], help='Model type')
    test_parser.add_argument('--parameters', help='JSON string of parameters')
    test_parser.add_argument('--variant', help='Variant name to use')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available prompts')
    list_parser.add_argument('--model-type', choices=['standard', 'reasoning'], help='Filter by model type')
    list_parser.add_argument('--category', help='Filter by category')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Get prompt information')
    info_parser.add_argument('--prompt', required=True, help='Prompt ID')
    info_parser.add_argument('--model-type', default='standard', choices=['standard', 'reasoning'], help='Model type')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare original vs JSON prompts')
    compare_parser.add_argument('--test', help='Specific test name to run')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export prompt catalog')
    export_parser.add_argument('--output', required=True, type=Path, help='Output file path')
    
    # Integration tests command
    subparsers.add_parser('integration', help='Run integration tests')
    
    # Performance tests command
    subparsers.add_parser('performance', help='Run performance and quality tests')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize CLI tools
    try:
        cli_tools = PromptCLITools()
    except Exception as e:
        print(f"❌ Failed to initialize CLI tools: {e}")
        return 1
    
    # Execute command
    try:
        if args.command == 'validate':
            if args.all:
                result = cli_tools.validate_all_prompts()
            else:
                result = cli_tools.validate_prompt(args.prompt, args.model_type)
            
            return 0 if result.get('valid', result.get('success_rate', 0) >= 80) else 1
        
        elif args.command == 'test':
            parameters = {}
            if args.parameters:
                try:
                    parameters = json.loads(args.parameters)
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON parameters: {e}")
                    return 1
            
            result = cli_tools.test_prompt_rendering(args.prompt, parameters, args.model_type, args.variant)
            return 0 if result['success'] else 1
        
        elif args.command == 'list':
            result = cli_tools.list_prompts(args.model_type, args.category)
            return 0 if result['success'] else 1
        
        elif args.command == 'info':
            result = cli_tools.get_prompt_info(args.prompt, args.model_type)
            return 0 if result['success'] else 1
        
        elif args.command == 'compare':
            result = cli_tools.compare_prompts(args.test)
            return 0 if result.get('success', result.get('success_rate', 0) >= 80) else 1
        
        elif args.command == 'export':
            result = cli_tools.export_catalog(args.output)
            return 0 if result['success'] else 1
        
        elif args.command == 'integration':
            result = cli_tools.run_integration_tests()
            return 0 if result.get('success_rate', 0) >= 80 else 1
        
        elif args.command == 'performance':
            result = cli_tools.run_performance_tests()
            return 0 if result.get('overall_success', False) else 1
        
        else:
            print(f"❌ Unknown command: {args.command}")
            return 1
    
    except Exception as e:
        print(f"❌ Command execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())