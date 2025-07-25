"""
Performance and Quality Validation Tests

This module provides comprehensive performance testing and quality validation
for the JSON prompt system, including benchmarks, memory usage analysis,
and quality metrics validation.
"""

import time
import psutil
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging
from datetime import datetime
import statistics
import json

from .json_prompt_manager import JsonPromptManager
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a test operation."""
    operation: str
    execution_time_ms: float
    memory_usage_mb: float
    cpu_percent: float
    cache_hit_rate: float
    success: bool
    error: Optional[str] = None


@dataclass
class QualityMetrics:
    """Quality metrics for prompt validation."""
    prompt_id: str
    schema_valid: bool
    examples_valid: bool
    parameter_coverage: float
    template_complexity: int
    quality_score: float
    issues: List[str]


class PerformanceQualityTester:
    """
    Comprehensive performance and quality testing for the JSON prompt system.
    
    Provides benchmarking, memory analysis, and quality validation
    to ensure the system meets performance and quality standards.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the performance and quality tester."""
        self.config = config or Config.from_env()
        self.manager = JsonPromptManager(self.config)
        self.performance_results: List[PerformanceMetrics] = []
        self.quality_results: List[QualityMetrics] = []
        
        # Performance thresholds
        self.thresholds = {
            'max_load_time_ms': 100,      # Max time to load a prompt
            'max_render_time_ms': 50,     # Max time to render a prompt
            'max_memory_usage_mb': 100,   # Max memory usage for operations
            'min_cache_hit_rate': 50,     # Min cache hit rate percentage
            'min_quality_score': 7.0      # Min quality score for prompts
        }
        
        logger.info("PerformanceQualityTester initialized")
    
    def benchmark_prompt_loading(self, iterations: int = 100) -> PerformanceMetrics:
        """Benchmark prompt loading performance."""
        operation = "prompt_loading"
        
        try:
            # Get available prompts
            available = self.manager.get_available_prompts()
            all_prompts = []
            for model_type, prompt_ids in available.items():
                for prompt_id in prompt_ids:
                    all_prompts.append((prompt_id, model_type))
            
            if not all_prompts:
                raise ValueError("No prompts available for benchmarking")
            
            # Clear cache to ensure cold start
            self.manager.clear_cache()
            
            # Measure memory before
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Benchmark loading
            start_time = time.time()
            cpu_times = []
            
            for i in range(iterations):
                # Select prompt cyclically
                prompt_id, model_type = all_prompts[i % len(all_prompts)]
                
                cpu_before = process.cpu_percent()
                self.manager.load_prompt(prompt_id, model_type)
                cpu_after = process.cpu_percent()
                
                cpu_times.append(cpu_after - cpu_before)
            
            end_time = time.time()
            
            # Measure memory after
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            
            # Get cache stats
            cache_stats = self.manager.get_cache_stats()
            
            execution_time_ms = (end_time - start_time) * 1000
            memory_usage_mb = memory_after - memory_before
            avg_cpu_percent = statistics.mean(cpu_times) if cpu_times else 0
            
            return PerformanceMetrics(
                operation=operation,
                execution_time_ms=execution_time_ms,
                memory_usage_mb=memory_usage_mb,
                cpu_percent=avg_cpu_percent,
                cache_hit_rate=cache_stats['hit_rate'],
                success=True
            )
            
        except Exception as e:
            return PerformanceMetrics(
                operation=operation,
                execution_time_ms=0,
                memory_usage_mb=0,
                cpu_percent=0,
                cache_hit_rate=0,
                success=False,
                error=str(e)
            )
    
    def benchmark_prompt_rendering(self, iterations: int = 100) -> PerformanceMetrics:
        """Benchmark prompt rendering performance."""
        operation = "prompt_rendering"
        
        try:
            # Define test cases for rendering
            test_cases = [
                ("categorization_standard", {
                    "context_content": "Test content for performance benchmarking",
                    "formatted_existing_categories": "test_category",
                    "is_thread": False
                }),
                ("chat_standard", {}),
                ("short_name_generation", {}),
                ("kb_item_generation_standard", {
                    "context_data": {
                        "tweet_text": "Performance test content",
                        "main_category": "test_category",
                        "sub_category": "test_subcategory",
                        "item_name": "test_item",
                        "all_urls": [],
                        "all_media_descriptions": []
                    }
                })
            ]
            
            # Measure memory before
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Benchmark rendering
            start_time = time.time()
            render_times = []
            cpu_times = []
            
            for i in range(iterations):
                prompt_id, params = test_cases[i % len(test_cases)]
                
                cpu_before = process.cpu_percent()
                render_start = time.time()
                
                result = self.manager.render_prompt(prompt_id, params)
                
                render_end = time.time()
                cpu_after = process.cpu_percent()
                
                render_times.append((render_end - render_start) * 1000)
                cpu_times.append(cpu_after - cpu_before)
            
            end_time = time.time()
            
            # Measure memory after
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            
            # Get cache stats
            cache_stats = self.manager.get_cache_stats()
            
            execution_time_ms = (end_time - start_time) * 1000
            memory_usage_mb = memory_after - memory_before
            avg_cpu_percent = statistics.mean(cpu_times) if cpu_times else 0
            avg_render_time = statistics.mean(render_times) if render_times else 0
            
            # Store individual render times for analysis
            metrics = PerformanceMetrics(
                operation=operation,
                execution_time_ms=execution_time_ms,
                memory_usage_mb=memory_usage_mb,
                cpu_percent=avg_cpu_percent,
                cache_hit_rate=cache_stats['hit_rate'],
                success=True
            )
            
            # Add additional metrics
            setattr(metrics, 'avg_render_time_ms', avg_render_time)
            setattr(metrics, 'max_render_time_ms', max(render_times) if render_times else 0)
            setattr(metrics, 'min_render_time_ms', min(render_times) if render_times else 0)
            
            return metrics
            
        except Exception as e:
            return PerformanceMetrics(
                operation=operation,
                execution_time_ms=0,
                memory_usage_mb=0,
                cpu_percent=0,
                cache_hit_rate=0,
                success=False,
                error=str(e)
            )
    
    def benchmark_concurrent_operations(self, num_threads: int = 10, operations_per_thread: int = 20) -> PerformanceMetrics:
        """Benchmark concurrent operations performance."""
        operation = "concurrent_operations"
        
        try:
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Test case for concurrent operations
            test_params = {
                "context_content": "Concurrent test content",
                "formatted_existing_categories": "test_category",
                "is_thread": False
            }
            
            # Measure memory before
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            def worker_function():
                """Worker function for concurrent testing."""
                times = []
                for _ in range(operations_per_thread):
                    start = time.time()
                    self.manager.render_prompt("categorization_standard", test_params)
                    end = time.time()
                    times.append((end - start) * 1000)
                return times
            
            # Run concurrent operations
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker_function) for _ in range(num_threads)]
                
                all_times = []
                for future in as_completed(futures):
                    times = future.result()
                    all_times.extend(times)
            
            end_time = time.time()
            
            # Measure memory after
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            
            # Get cache stats
            cache_stats = self.manager.get_cache_stats()
            
            execution_time_ms = (end_time - start_time) * 1000
            memory_usage_mb = memory_after - memory_before
            cpu_percent = process.cpu_percent()
            
            total_operations = num_threads * operations_per_thread
            avg_operation_time = statistics.mean(all_times) if all_times else 0
            
            metrics = PerformanceMetrics(
                operation=operation,
                execution_time_ms=execution_time_ms,
                memory_usage_mb=memory_usage_mb,
                cpu_percent=cpu_percent,
                cache_hit_rate=cache_stats['hit_rate'],
                success=True
            )
            
            # Add additional metrics
            setattr(metrics, 'total_operations', total_operations)
            setattr(metrics, 'operations_per_second', total_operations / (execution_time_ms / 1000))
            setattr(metrics, 'avg_operation_time_ms', avg_operation_time)
            
            return metrics
            
        except Exception as e:
            return PerformanceMetrics(
                operation=operation,
                execution_time_ms=0,
                memory_usage_mb=0,
                cpu_percent=0,
                cache_hit_rate=0,
                success=False,
                error=str(e)
            )
    
    def benchmark_memory_usage(self) -> PerformanceMetrics:
        """Benchmark memory usage patterns."""
        operation = "memory_usage"
        
        try:
            process = psutil.Process()
            
            # Measure baseline memory
            gc.collect()  # Force garbage collection
            baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Load all prompts and measure memory growth
            available = self.manager.get_available_prompts()
            memory_samples = [baseline_memory]
            
            start_time = time.time()
            
            for model_type, prompt_ids in available.items():
                for prompt_id in prompt_ids:
                    self.manager.load_prompt(prompt_id, model_type)
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory)
            
            # Render multiple prompts and measure memory
            for _ in range(50):
                self.manager.render_prompt("chat_standard", {})
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
            
            end_time = time.time()
            
            # Calculate memory statistics
            max_memory = max(memory_samples)
            avg_memory = statistics.mean(memory_samples)
            memory_growth = max_memory - baseline_memory
            
            # Get cache stats
            cache_stats = self.manager.get_cache_stats()
            
            execution_time_ms = (end_time - start_time) * 1000
            
            metrics = PerformanceMetrics(
                operation=operation,
                execution_time_ms=execution_time_ms,
                memory_usage_mb=memory_growth,
                cpu_percent=process.cpu_percent(),
                cache_hit_rate=cache_stats['hit_rate'],
                success=True
            )
            
            # Add additional metrics
            setattr(metrics, 'baseline_memory_mb', baseline_memory)
            setattr(metrics, 'max_memory_mb', max_memory)
            setattr(metrics, 'avg_memory_mb', avg_memory)
            setattr(metrics, 'memory_samples', len(memory_samples))
            
            return metrics
            
        except Exception as e:
            return PerformanceMetrics(
                operation=operation,
                execution_time_ms=0,
                memory_usage_mb=0,
                cpu_percent=0,
                cache_hit_rate=0,
                success=False,
                error=str(e)
            )
    
    def validate_prompt_quality(self, prompt_id: str, model_type: str = "standard") -> QualityMetrics:
        """Validate quality metrics for a specific prompt."""
        try:
            # Load prompt
            prompt = self.manager.load_prompt(prompt_id, model_type)
            issues = []
            
            # Schema validation
            schema_valid = True
            try:
                # Prompt loading already validates schema
                pass
            except Exception as e:
                schema_valid = False
                issues.append(f"Schema validation failed: {e}")
            
            # Examples validation
            examples_valid = True
            examples = prompt.get_examples()
            
            if examples:
                for i, example in enumerate(examples):
                    try:
                        prompt.render(example['input'])
                    except Exception as e:
                        examples_valid = False
                        issues.append(f"Example {i+1} failed: {e}")
            
            # Parameter coverage analysis
            required_params = prompt.required_parameters
            optional_params = prompt.optional_parameters
            all_params = required_params + optional_params
            
            # Check if examples cover all parameters
            covered_params = set()
            if examples:
                for example in examples:
                    covered_params.update(example['input'].keys())
            
            parameter_coverage = len(covered_params) / max(1, len(all_params)) * 100
            
            if parameter_coverage < 80:
                issues.append(f"Low parameter coverage: {parameter_coverage:.1f}%")
            
            # Template complexity analysis
            template_content = ""
            if hasattr(prompt, 'prompt_data'):
                template = prompt.prompt_data.get('template', {})
                if template.get('type') == 'standard':
                    template_content = template.get('content', '')
                elif template.get('type') == 'reasoning':
                    template_content = template.get('user_message', '') + template.get('system_message', '')
            
            template_complexity = len(template_content.split('{{')) - 1  # Count template variables
            
            # Calculate quality score
            quality_score = 10.0
            
            if not schema_valid:
                quality_score -= 3.0
            if not examples_valid:
                quality_score -= 2.0
            if parameter_coverage < 50:
                quality_score -= 2.0
            elif parameter_coverage < 80:
                quality_score -= 1.0
            if template_complexity < 2:
                quality_score -= 1.0
            if len(issues) > 3:
                quality_score -= 1.0
            
            quality_score = max(0.0, quality_score)
            
            return QualityMetrics(
                prompt_id=prompt_id,
                schema_valid=schema_valid,
                examples_valid=examples_valid,
                parameter_coverage=parameter_coverage,
                template_complexity=template_complexity,
                quality_score=quality_score,
                issues=issues
            )
            
        except Exception as e:
            return QualityMetrics(
                prompt_id=prompt_id,
                schema_valid=False,
                examples_valid=False,
                parameter_coverage=0.0,
                template_complexity=0,
                quality_score=0.0,
                issues=[f"Quality validation failed: {e}"]
            )
    
    def run_performance_benchmarks(self) -> Dict[str, Any]:
        """Run all performance benchmarks."""
        logger.info("Starting performance benchmarks")
        
        benchmarks = [
            ("prompt_loading", lambda: self.benchmark_prompt_loading(50)),
            ("prompt_rendering", lambda: self.benchmark_prompt_rendering(100)),
            ("concurrent_operations", lambda: self.benchmark_concurrent_operations(5, 10)),
            ("memory_usage", lambda: self.benchmark_memory_usage())
        ]
        
        self.performance_results = []
        
        for name, benchmark_func in benchmarks:
            logger.info(f"Running {name} benchmark...")
            result = benchmark_func()
            self.performance_results.append(result)
            
            if result.success:
                logger.info(f"✅ {name}: {result.execution_time_ms:.2f}ms, {result.memory_usage_mb:.2f}MB")
            else:
                logger.error(f"❌ {name}: {result.error}")
        
        # Analyze results against thresholds
        performance_summary = self._analyze_performance_results()
        
        return performance_summary
    
    def run_quality_validation(self) -> Dict[str, Any]:
        """Run quality validation for all prompts."""
        logger.info("Starting quality validation")
        
        available = self.manager.get_available_prompts()
        self.quality_results = []
        
        for model_type, prompt_ids in available.items():
            for prompt_id in prompt_ids:
                logger.info(f"Validating quality for {prompt_id} ({model_type})")
                result = self.validate_prompt_quality(prompt_id, model_type)
                self.quality_results.append(result)
        
        # Analyze quality results
        quality_summary = self._analyze_quality_results()
        
        return quality_summary
    
    def _analyze_performance_results(self) -> Dict[str, Any]:
        """Analyze performance results against thresholds."""
        passed_tests = 0
        failed_tests = 0
        performance_issues = []
        
        for result in self.performance_results:
            if not result.success:
                failed_tests += 1
                performance_issues.append(f"{result.operation}: {result.error}")
                continue
            
            # Check against thresholds
            issues_found = False
            
            if hasattr(result, 'avg_render_time_ms') and result.avg_render_time_ms > self.thresholds['max_render_time_ms']:
                issues_found = True
                performance_issues.append(f"{result.operation}: Average render time too high ({result.avg_render_time_ms:.2f}ms)")
            
            if result.memory_usage_mb > self.thresholds['max_memory_usage_mb']:
                issues_found = True
                performance_issues.append(f"{result.operation}: Memory usage too high ({result.memory_usage_mb:.2f}MB)")
            
            if result.cache_hit_rate < self.thresholds['min_cache_hit_rate']:
                issues_found = True
                performance_issues.append(f"{result.operation}: Cache hit rate too low ({result.cache_hit_rate:.1f}%)")
            
            if issues_found:
                failed_tests += 1
            else:
                passed_tests += 1
        
        return {
            'total_benchmarks': len(self.performance_results),
            'passed': passed_tests,
            'failed': failed_tests,
            'success_rate': (passed_tests / len(self.performance_results)) * 100 if self.performance_results else 0,
            'performance_issues': performance_issues,
            'results': self.performance_results
        }
    
    def _analyze_quality_results(self) -> Dict[str, Any]:
        """Analyze quality results against standards."""
        high_quality = 0
        medium_quality = 0
        low_quality = 0
        quality_issues = []
        
        for result in self.quality_results:
            if result.quality_score >= 8.0:
                high_quality += 1
            elif result.quality_score >= self.thresholds['min_quality_score']:
                medium_quality += 1
            else:
                low_quality += 1
                quality_issues.append(f"{result.prompt_id}: Quality score too low ({result.quality_score:.1f})")
        
        avg_quality_score = statistics.mean([r.quality_score for r in self.quality_results]) if self.quality_results else 0
        
        return {
            'total_prompts': len(self.quality_results),
            'high_quality': high_quality,
            'medium_quality': medium_quality,
            'low_quality': low_quality,
            'avg_quality_score': avg_quality_score,
            'quality_issues': quality_issues,
            'results': self.quality_results
        }
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance and quality tests."""
        logger.info("Starting comprehensive performance and quality tests")
        
        # Run performance benchmarks
        performance_summary = self.run_performance_benchmarks()
        
        # Run quality validation
        quality_summary = self.run_quality_validation()
        
        # Overall summary
        overall_summary = {
            'timestamp': datetime.now().isoformat(),
            'performance': performance_summary,
            'quality': quality_summary,
            'thresholds': self.thresholds,
            'overall_success': (
                performance_summary['success_rate'] >= 80 and
                quality_summary['avg_quality_score'] >= self.thresholds['min_quality_score']
            )
        }
        
        logger.info(f"Performance tests: {performance_summary['success_rate']:.1f}% success rate")
        logger.info(f"Quality validation: {quality_summary['avg_quality_score']:.1f} average score")
        logger.info(f"Overall success: {overall_summary['overall_success']}")
        
        return overall_summary
    
    def generate_performance_report(self, output_file: Optional[Path] = None) -> str:
        """Generate detailed performance and quality report."""
        if not self.performance_results and not self.quality_results:
            return "No test results available. Run tests first."
        
        report_lines = [
            "# Performance and Quality Validation Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Performance Benchmarks",
            ""
        ]
        
        # Performance results
        if self.performance_results:
            for result in self.performance_results:
                status = "✅ PASSED" if result.success else "❌ FAILED"
                report_lines.extend([
                    f"### {result.operation}",
                    f"**Status:** {status}",
                    f"**Execution Time:** {result.execution_time_ms:.2f}ms",
                    f"**Memory Usage:** {result.memory_usage_mb:.2f}MB",
                    f"**CPU Usage:** {result.cpu_percent:.1f}%",
                    f"**Cache Hit Rate:** {result.cache_hit_rate:.1f}%",
                    ""
                ])
                
                if result.error:
                    report_lines.extend([
                        f"**Error:** {result.error}",
                        ""
                    ])
                
                # Add additional metrics if available
                if hasattr(result, 'avg_render_time_ms'):
                    report_lines.extend([
                        f"**Average Render Time:** {result.avg_render_time_ms:.2f}ms",
                        f"**Max Render Time:** {result.max_render_time_ms:.2f}ms",
                        f"**Min Render Time:** {result.min_render_time_ms:.2f}ms",
                        ""
                    ])
        
        # Quality results
        report_lines.extend([
            "## Quality Validation",
            ""
        ])
        
        if self.quality_results:
            for result in self.quality_results:
                status = "✅ HIGH" if result.quality_score >= 8.0 else "🔶 MEDIUM" if result.quality_score >= 7.0 else "❌ LOW"
                report_lines.extend([
                    f"### {result.prompt_id}",
                    f"**Quality Score:** {result.quality_score:.1f}/10 ({status})",
                    f"**Schema Valid:** {'✅' if result.schema_valid else '❌'}",
                    f"**Examples Valid:** {'✅' if result.examples_valid else '❌'}",
                    f"**Parameter Coverage:** {result.parameter_coverage:.1f}%",
                    f"**Template Complexity:** {result.template_complexity} variables",
                    ""
                ])
                
                if result.issues:
                    report_lines.extend([
                        "**Issues:**",
                        ""
                    ])
                    for issue in result.issues:
                        report_lines.append(f"- {issue}")
                    report_lines.append("")
        
        report = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Performance report written to: {output_file}")
        
        return report