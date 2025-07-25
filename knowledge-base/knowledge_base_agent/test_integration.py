"""
Integration Tests for JSON Prompt System

This module provides comprehensive integration tests that validate the JSON prompt system
with actual Config objects, environment variables, and real-world usage scenarios.
"""

import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass
from datetime import datetime

from .config import Config
from .json_prompt_manager import JsonPromptManager, JsonPromptManagerError
from .json_prompt import JsonPrompt, JsonPromptError

logger = logging.getLogger(__name__)


@dataclass
class IntegrationTestResult:
    """Result of an integration test."""
    test_name: str
    passed: bool
    error: Optional[str] = None
    details: Dict[str, Any] = None


class IntegrationTester:
    """
    Comprehensive integration testing for the JSON prompt system.
    
    Tests the system with real Config objects, environment variables,
    and production-like scenarios.
    """
    
    def __init__(self):
        """Initialize the integration tester."""
        self.results: List[IntegrationTestResult] = []
        self.temp_dirs: List[Path] = []
        
    def cleanup(self):
        """Clean up temporary directories and files."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
        self.temp_dirs.clear()
    
    def test_config_integration(self) -> IntegrationTestResult:
        """Test integration with Config objects."""
        test_name = "config_integration"
        
        try:
            # Test with default config
            config = Config.from_env()
            manager = JsonPromptManager(config)
            
            # Verify manager initialization
            assert manager.config is config
            assert manager.prompts_dir.exists()
            assert manager.schema_file.exists()
            
            # Test prompt loading with config
            available = manager.get_available_prompts()
            assert len(available['standard']) > 0
            assert len(available['reasoning']) > 0
            
            # Test rendering with config context
            result = manager.render_prompt(
                "chat_standard",
                {},
                "standard"
            )
            assert len(result.content) > 0
            assert result.prompt_id == "chat_standard"
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'config_type': type(config).__name__,
                    'prompts_dir': str(manager.prompts_dir),
                    'available_prompts': sum(len(prompts) for prompts in available.values())
                }
            )
            
        except Exception as e:
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def test_environment_variables(self) -> IntegrationTestResult:
        """Test behavior with different environment variable configurations."""
        test_name = "environment_variables"
        
        try:
            # Save original environment
            original_env = dict(os.environ)
            
            # Test with modified environment
            test_env = {
                'PROJECT_ROOT': str(Path.cwd()),
                'DATA_PROCESSING_DIR': 'test_data',
                'OLLAMA_BASE_URL': 'http://test-ollama:11434'
            }
            
            # Update environment
            os.environ.update(test_env)
            
            # Create config with test environment
            config = Config.from_env()
            manager = JsonPromptManager(config)
            
            # Verify environment integration
            assert config.project_root == Path.cwd()
            assert str(config.data_processing_dir).endswith('test_data')
            
            # Test prompt operations work with modified environment
            result = manager.render_prompt(
                "categorization_standard",
                {
                    "context_content": "Test content for environment integration",
                    "formatted_existing_categories": "test_category",
                    "is_thread": False
                }
            )
            
            assert len(result.content) > 0
            assert "Test content for environment integration" in result.content
            
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'test_env_vars': list(test_env.keys()),
                    'config_project_root': str(config.project_root),
                    'render_success': True
                }
            )
            
        except Exception as e:
            # Restore original environment on error
            os.environ.clear()
            os.environ.update(original_env)
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def test_custom_prompts_directory(self) -> IntegrationTestResult:
        """Test with custom prompts directory configuration."""
        test_name = "custom_prompts_directory"
        
        try:
            # Create temporary directory structure
            temp_dir = Path(tempfile.mkdtemp())
            self.temp_dirs.append(temp_dir)
            
            prompts_dir = temp_dir / "custom_prompts"
            prompts_dir.mkdir()
            
            # Create standard and reasoning subdirectories
            (prompts_dir / "standard").mkdir()
            (prompts_dir / "reasoning").mkdir()
            
            # Create a simple test prompt
            test_prompt = {
                "prompt_id": "test_prompt",
                "prompt_name": "Test Prompt",
                "description": "A test prompt for integration testing",
                "model_type": "standard",
                "category": "chat",
                "task": "Test task",
                "input_parameters": {
                    "required": [],
                    "optional": [],
                    "parameters": {}
                },
                "template": {
                    "type": "standard",
                    "content": "This is a test prompt for integration testing."
                }
            }
            
            # Write test prompt file
            with open(prompts_dir / "standard" / "test_prompt.json", 'w') as f:
                json.dump(test_prompt, f, indent=2)
            
            # Create config file
            config_data = {
                "schema_version": "1.0.0",
                "description": "Test configuration"
            }
            
            with open(prompts_dir / "config.json", 'w') as f:
                json.dump(config_data, f, indent=2)
            
            # Copy schema file from main system
            import shutil
            main_schema = Path(__file__).parent / "prompt_schema.json"
            if main_schema.exists():
                shutil.copy(main_schema, temp_dir / "prompt_schema.json")
            
            # Test with custom directory
            manager = JsonPromptManager(prompts_dir=prompts_dir)
            
            # Verify custom directory is used
            assert manager.prompts_dir == prompts_dir
            
            # Test loading custom prompt
            available = manager.get_available_prompts()
            assert "test_prompt" in available['standard']
            
            # Test rendering custom prompt
            result = manager.render_prompt("test_prompt", {})
            assert result.content == "This is a test prompt for integration testing."
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'custom_dir': str(prompts_dir),
                    'test_prompt_loaded': True,
                    'render_success': True
                }
            )
            
        except Exception as e:
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def test_file_system_integration(self) -> IntegrationTestResult:
        """Test file system operations and path handling."""
        test_name = "file_system_integration"
        
        try:
            config = Config.from_env()
            manager = JsonPromptManager(config)
            
            # Test file system operations
            prompts_dir = manager.prompts_dir
            schema_file = manager.schema_file
            
            # Verify paths exist and are accessible
            assert prompts_dir.exists() and prompts_dir.is_dir()
            assert schema_file.exists() and schema_file.is_file()
            
            # Test directory structure
            standard_dir = prompts_dir / "standard"
            reasoning_dir = prompts_dir / "reasoning"
            
            assert standard_dir.exists() and standard_dir.is_dir()
            assert reasoning_dir.exists() and reasoning_dir.is_dir()
            
            # Test file discovery
            standard_files = list(standard_dir.glob("*.json"))
            reasoning_files = list(reasoning_dir.glob("*.json"))
            
            assert len(standard_files) > 0
            assert len(reasoning_files) > 0
            
            # Test file loading and parsing
            test_file = standard_files[0]
            with open(test_file, 'r') as f:
                prompt_data = json.load(f)
            
            # Verify required fields
            required_fields = ['prompt_id', 'prompt_name', 'description', 'model_type']
            for field in required_fields:
                assert field in prompt_data
            
            # Test schema file loading
            with open(schema_file, 'r') as f:
                schema_data = json.load(f)
            
            assert '$schema' in schema_data
            assert 'properties' in schema_data
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'prompts_dir': str(prompts_dir),
                    'schema_file': str(schema_file),
                    'standard_files': len(standard_files),
                    'reasoning_files': len(reasoning_files),
                    'schema_valid': True
                }
            )
            
        except Exception as e:
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def test_concurrent_operations(self) -> IntegrationTestResult:
        """Test concurrent prompt operations."""
        test_name = "concurrent_operations"
        
        try:
            import threading
            import time
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            manager = JsonPromptManager()
            results = []
            errors = []
            
            def render_prompt_worker(prompt_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
                """Worker function for concurrent prompt rendering."""
                try:
                    result = manager.render_prompt(prompt_id, params)
                    return {
                        'success': True,
                        'prompt_id': prompt_id,
                        'content_length': len(result.content),
                        'render_time': result.render_time_ms
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'prompt_id': prompt_id,
                        'error': str(e)
                    }
            
            # Define concurrent test cases
            test_cases = [
                ("chat_standard", {}),
                ("categorization_standard", {
                    "context_content": "Test content 1",
                    "formatted_existing_categories": "test",
                    "is_thread": False
                }),
                ("categorization_standard", {
                    "context_content": "Test content 2", 
                    "formatted_existing_categories": "test",
                    "is_thread": True
                }),
                ("short_name_generation", {}),
                ("chat_synthesis_aware", {})
            ]
            
            # Run concurrent operations
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(render_prompt_worker, prompt_id, params)
                    for prompt_id, params in test_cases
                ]
                
                for future in as_completed(futures):
                    result = future.result()
                    if result['success']:
                        results.append(result)
                    else:
                        errors.append(result)
            
            # Verify results
            assert len(results) > 0, "No successful concurrent operations"
            assert len(errors) == 0, f"Concurrent operations had errors: {errors}"
            
            # Test cache performance under concurrency
            cache_stats = manager.get_cache_stats()
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'successful_operations': len(results),
                    'failed_operations': len(errors),
                    'cache_hits': cache_stats['cache_hits'],
                    'cache_misses': cache_stats['cache_misses'],
                    'hit_rate': cache_stats['hit_rate']
                }
            )
            
        except Exception as e:
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def test_error_handling_integration(self) -> IntegrationTestResult:
        """Test error handling in integration scenarios."""
        test_name = "error_handling_integration"
        
        try:
            manager = JsonPromptManager()
            error_scenarios = []
            
            # Test 1: Invalid prompt ID
            try:
                manager.load_prompt("nonexistent_prompt")
                error_scenarios.append("Should have failed for nonexistent prompt")
            except JsonPromptManagerError:
                pass  # Expected
            
            # Test 2: Invalid parameters
            try:
                manager.render_prompt("categorization_standard", {})  # Missing required params
                error_scenarios.append("Should have failed for missing parameters")
            except JsonPromptManagerError:
                pass  # Expected
            
            # Test 3: Invalid model type
            try:
                manager.load_prompt("chat_standard", "invalid_model_type")
                error_scenarios.append("Should have failed for invalid model type")
            except JsonPromptManagerError:
                pass  # Expected
            
            # Test 4: Corrupted prompt file (simulate by creating invalid JSON)
            temp_dir = Path(tempfile.mkdtemp())
            self.temp_dirs.append(temp_dir)
            
            (temp_dir / "standard").mkdir(parents=True)
            
            # Write invalid JSON
            with open(temp_dir / "standard" / "invalid.json", 'w') as f:
                f.write("{ invalid json content")
            
            temp_manager = JsonPromptManager(prompts_dir=temp_dir)
            try:
                temp_manager.load_prompt("invalid")
                error_scenarios.append("Should have failed for invalid JSON")
            except JsonPromptManagerError:
                pass  # Expected
            
            # Verify no unexpected errors occurred
            assert len(error_scenarios) == 0, f"Unexpected error handling: {error_scenarios}"
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'error_scenarios_tested': 4,
                    'unexpected_errors': len(error_scenarios)
                }
            )
            
        except Exception as e:
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def test_performance_integration(self) -> IntegrationTestResult:
        """Test performance characteristics in integration scenarios."""
        test_name = "performance_integration"
        
        try:
            import time
            
            manager = JsonPromptManager()
            
            # Test cold start performance
            start_time = time.time()
            result1 = manager.render_prompt("chat_standard", {})
            cold_start_time = time.time() - start_time
            
            # Test warm cache performance
            start_time = time.time()
            result2 = manager.render_prompt("chat_standard", {})
            warm_cache_time = time.time() - start_time
            
            # Test preloading performance
            start_time = time.time()
            preload_results = manager.preload_prompts(["standard"])
            preload_time = time.time() - start_time
            
            # Test bulk operations
            start_time = time.time()
            for i in range(10):
                manager.render_prompt("short_name_generation", {})
            bulk_time = time.time() - start_time
            
            # Get final cache stats
            cache_stats = manager.get_cache_stats()
            
            # Performance assertions
            assert cold_start_time < 1.0, f"Cold start too slow: {cold_start_time:.3f}s"
            assert warm_cache_time < cold_start_time, "Warm cache should be faster than cold start"
            assert bulk_time < 1.0, f"Bulk operations too slow: {bulk_time:.3f}s"
            
            return IntegrationTestResult(
                test_name=test_name,
                passed=True,
                details={
                    'cold_start_time_ms': cold_start_time * 1000,
                    'warm_cache_time_ms': warm_cache_time * 1000,
                    'preload_time_ms': preload_time * 1000,
                    'bulk_time_ms': bulk_time * 1000,
                    'preloaded_prompts': preload_results['loaded'],
                    'cache_hit_rate': cache_stats['hit_rate']
                }
            )
            
        except Exception as e:
            return IntegrationTestResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            )
    
    def run_all_integration_tests(self) -> Dict[str, Any]:
        """Run all integration tests and return comprehensive results."""
        logger.info("Starting comprehensive integration tests")
        
        test_methods = [
            self.test_config_integration,
            self.test_environment_variables,
            self.test_custom_prompts_directory,
            self.test_file_system_integration,
            self.test_concurrent_operations,
            self.test_error_handling_integration,
            self.test_performance_integration
        ]
        
        self.results = []
        passed = 0
        failed = 0
        
        for test_method in test_methods:
            try:
                result = test_method()
                self.results.append(result)
                
                if result.passed:
                    passed += 1
                    logger.info(f"✅ {result.test_name}: PASSED")
                else:
                    failed += 1
                    logger.error(f"❌ {result.test_name}: FAILED - {result.error}")
                    
            except Exception as e:
                failed += 1
                error_result = IntegrationTestResult(
                    test_name=test_method.__name__,
                    passed=False,
                    error=str(e)
                )
                self.results.append(error_result)
                logger.error(f"❌ {test_method.__name__}: CRASHED - {e}")
        
        # Cleanup
        self.cleanup()
        
        # Generate summary
        total_tests = len(test_methods)
        summary = {
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / total_tests) * 100,
            'test_results': self.results
        }
        
        logger.info(f"Integration Test Summary: {passed}/{total_tests} passed ({summary['success_rate']:.1f}%)")
        
        return summary
    
    def generate_integration_report(self, output_file: Optional[Path] = None) -> str:
        """Generate detailed integration test report."""
        if not self.results:
            return "No integration test results available. Run tests first."
        
        report_lines = [
            "# Integration Test Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Total Tests: {len(self.results)}",
            "",
            "## Summary",
        ]
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        report_lines.extend([
            f"- ✅ Passed: {passed}",
            f"- ❌ Failed: {failed}",
            f"- 📈 Success Rate: {(passed / len(self.results)) * 100:.1f}%",
            "",
            "## Detailed Results",
            ""
        ])
        
        for result in self.results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            report_lines.extend([
                f"### {result.test_name}",
                f"**Status:** {status}",
                ""
            ])
            
            if result.error:
                report_lines.extend([
                    f"**Error:** {result.error}",
                    ""
                ])
            
            if result.details:
                report_lines.extend([
                    "**Details:**",
                    "```json"
                ])
                report_lines.append(json.dumps(result.details, indent=2))
                report_lines.extend(["```", ""])
        
        report = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Integration report written to: {output_file}")
        
        return report