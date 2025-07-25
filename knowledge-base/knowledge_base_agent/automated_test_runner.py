"""
Automated Test Execution Framework

This module provides a comprehensive automated test runner for the JSON prompt system,
including continuous integration support, regression testing, and comprehensive reporting.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
import subprocess
import sys

from .test_prompt_comparison import PromptComparisonTester
from .test_integration import IntegrationTester
from .test_performance_quality import PerformanceQualityTester
from .json_prompt_manager import JsonPromptManager
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class TestSuiteResult:
    """Result of a complete test suite execution."""
    suite_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    success_rate: float
    details: Dict[str, Any]
    errors: List[str]


class AutomatedTestRunner:
    """
    Comprehensive automated test execution framework.
    
    Provides continuous integration support, regression testing,
    and comprehensive reporting for the JSON prompt system.
    """
    
    def __init__(self, config: Optional[Config] = None, output_dir: Optional[Path] = None):
        """Initialize the automated test runner."""
        self.config = config or Config.from_env()
        self.output_dir = output_dir or Path("test_reports")
        self.output_dir.mkdir(exist_ok=True)
        
        # Test suite results
        self.suite_results: List[TestSuiteResult] = []
        
        # Test configuration
        self.test_config = {
            'comparison_tests': True,
            'integration_tests': True,
            'performance_tests': True,
            'quality_validation': True,
            'prompt_validation': True,
            'regression_threshold': 95.0,  # Minimum success rate for regression
            'performance_threshold': 80.0,  # Minimum performance success rate
            'quality_threshold': 7.0       # Minimum quality score
        }
        
        logger.info(f"AutomatedTestRunner initialized with output directory: {self.output_dir}")
    
    def run_prompt_validation_suite(self) -> TestSuiteResult:
        """Run comprehensive prompt validation tests."""
        suite_name = "prompt_validation"
        start_time = datetime.now()
        
        logger.info("Running prompt validation test suite...")
        
        try:
            manager = JsonPromptManager(self.config)
            available = manager.get_available_prompts()
            
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            validation_details = {}
            errors = []
            
            for model_type, prompt_ids in available.items():
                for prompt_id in prompt_ids:
                    total_tests += 1
                    
                    try:
                        validation_result = manager.validate_prompt(prompt_id, model_type)
                        validation_details[f"{model_type}:{prompt_id}"] = validation_result
                        
                        if validation_result['valid']:
                            passed_tests += 1
                        else:
                            failed_tests += 1
                            errors.extend(validation_result.get('errors', []))
                            
                    except Exception as e:
                        failed_tests += 1
                        error_msg = f"Validation failed for {model_type}:{prompt_id}: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            result = TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                success_rate=success_rate,
                details=validation_details,
                errors=errors
            )
            
            logger.info(f"Prompt validation suite completed: {success_rate:.1f}% success rate")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = f"Prompt validation suite failed: {e}"
            logger.error(error_msg)
            
            return TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                success_rate=0.0,
                details={},
                errors=[error_msg]
            )
    
    def run_comparison_test_suite(self) -> TestSuiteResult:
        """Run prompt comparison test suite."""
        suite_name = "comparison_tests"
        start_time = datetime.now()
        
        logger.info("Running comparison test suite...")
        
        try:
            tester = PromptComparisonTester(self.config)
            summary = tester.run_all_tests()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Extract test details
            test_details = {}
            errors = []
            
            for result in summary['test_results']:
                test_details[result.test_name] = {
                    'identical': result.identical,
                    'similarity_score': result.similarity_score,
                    'differences_count': len(result.differences),
                    'error': result.error
                }
                
                if result.error:
                    errors.append(f"{result.test_name}: {result.error}")
            
            result = TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=summary['total_tests'],
                passed_tests=summary['identical'] + summary['high_similarity'],
                failed_tests=summary['failed'],
                success_rate=summary['success_rate'],
                details=test_details,
                errors=errors
            )
            
            logger.info(f"Comparison test suite completed: {summary['success_rate']:.1f}% success rate")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = f"Comparison test suite failed: {e}"
            logger.error(error_msg)
            
            return TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                success_rate=0.0,
                details={},
                errors=[error_msg]
            )
    
    def run_integration_test_suite(self) -> TestSuiteResult:
        """Run integration test suite."""
        suite_name = "integration_tests"
        start_time = datetime.now()
        
        logger.info("Running integration test suite...")
        
        try:
            tester = IntegrationTester()
            summary = tester.run_all_integration_tests()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Extract test details
            test_details = {}
            errors = []
            
            for result in summary['test_results']:
                test_details[result.test_name] = {
                    'passed': result.passed,
                    'error': result.error,
                    'details': result.details
                }
                
                if result.error:
                    errors.append(f"{result.test_name}: {result.error}")
            
            result = TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=summary['total_tests'],
                passed_tests=summary['passed'],
                failed_tests=summary['failed'],
                success_rate=summary['success_rate'],
                details=test_details,
                errors=errors
            )
            
            logger.info(f"Integration test suite completed: {summary['success_rate']:.1f}% success rate")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = f"Integration test suite failed: {e}"
            logger.error(error_msg)
            
            return TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                success_rate=0.0,
                details={},
                errors=[error_msg]
            )
    
    def run_performance_test_suite(self) -> TestSuiteResult:
        """Run performance and quality test suite."""
        suite_name = "performance_quality"
        start_time = datetime.now()
        
        logger.info("Running performance and quality test suite...")
        
        try:
            tester = PerformanceQualityTester(self.config)
            summary = tester.run_comprehensive_tests()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Calculate overall metrics
            perf_success_rate = summary['performance']['success_rate']
            quality_avg_score = summary['quality']['avg_quality_score']
            
            # Determine pass/fail based on thresholds
            perf_passed = perf_success_rate >= self.test_config['performance_threshold']
            quality_passed = quality_avg_score >= self.test_config['quality_threshold']
            
            total_tests = 2  # Performance and quality
            passed_tests = sum([perf_passed, quality_passed])
            failed_tests = total_tests - passed_tests
            overall_success_rate = (passed_tests / total_tests) * 100
            
            # Collect errors
            errors = []
            errors.extend(summary['performance']['performance_issues'])
            errors.extend(summary['quality']['quality_issues'])
            
            result = TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                success_rate=overall_success_rate,
                details={
                    'performance_success_rate': perf_success_rate,
                    'quality_avg_score': quality_avg_score,
                    'performance_results': summary['performance'],
                    'quality_results': summary['quality']
                },
                errors=errors
            )
            
            logger.info(f"Performance test suite completed: {overall_success_rate:.1f}% success rate")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = f"Performance test suite failed: {e}"
            logger.error(error_msg)
            
            return TestSuiteResult(
                suite_name=suite_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                success_rate=0.0,
                details={},
                errors=[error_msg]
            )
    
    def run_all_test_suites(self) -> Dict[str, Any]:
        """Run all test suites and generate comprehensive report."""
        logger.info("Starting comprehensive automated test execution...")
        
        overall_start_time = datetime.now()
        self.suite_results = []
        
        # Define test suites to run
        test_suites = []
        
        if self.test_config['prompt_validation']:
            test_suites.append(('prompt_validation', self.run_prompt_validation_suite))
        
        if self.test_config['comparison_tests']:
            test_suites.append(('comparison_tests', self.run_comparison_test_suite))
        
        if self.test_config['integration_tests']:
            test_suites.append(('integration_tests', self.run_integration_test_suite))
        
        if self.test_config['performance_tests']:
            test_suites.append(('performance_quality', self.run_performance_test_suite))
        
        # Execute test suites
        for suite_name, suite_func in test_suites:
            logger.info(f"Executing test suite: {suite_name}")
            result = suite_func()
            self.suite_results.append(result)
        
        overall_end_time = datetime.now()
        overall_duration = (overall_end_time - overall_start_time).total_seconds()
        
        # Calculate overall statistics
        total_tests = sum(result.total_tests for result in self.suite_results)
        total_passed = sum(result.passed_tests for result in self.suite_results)
        total_failed = sum(result.failed_tests for result in self.suite_results)
        overall_success_rate = (total_passed / total_tests) * 100 if total_tests > 0 else 0
        
        # Collect all errors
        all_errors = []
        for result in self.suite_results:
            all_errors.extend(result.errors)
        
        # Determine regression status
        regression_passed = overall_success_rate >= self.test_config['regression_threshold']
        
        # Generate summary
        summary = {
            'execution_time': {
                'start_time': overall_start_time.isoformat(),
                'end_time': overall_end_time.isoformat(),
                'duration_seconds': overall_duration
            },
            'overall_statistics': {
                'total_test_suites': len(self.suite_results),
                'total_tests': total_tests,
                'total_passed': total_passed,
                'total_failed': total_failed,
                'success_rate': overall_success_rate,
                'regression_passed': regression_passed
            },
            'suite_results': [asdict(result) for result in self.suite_results],
            'errors': all_errors,
            'test_config': self.test_config
        }
        
        logger.info(f"Automated test execution completed:")
        logger.info(f"  Total Tests: {total_tests}")
        logger.info(f"  Passed: {total_passed}")
        logger.info(f"  Failed: {total_failed}")
        logger.info(f"  Success Rate: {overall_success_rate:.1f}%")
        logger.info(f"  Regression Status: {'✅ PASSED' if regression_passed else '❌ FAILED'}")
        
        return summary
    
    def generate_comprehensive_report(self, summary: Dict[str, Any], output_file: Optional[Path] = None) -> str:
        """Generate comprehensive test execution report."""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"test_report_{timestamp}.md"
        
        report_lines = [
            "# Automated Test Execution Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Duration: {summary['execution_time']['duration_seconds']:.2f} seconds",
            "",
            "## Executive Summary",
            ""
        ]
        
        stats = summary['overall_statistics']
        report_lines.extend([
            f"- **Total Test Suites:** {stats['total_test_suites']}",
            f"- **Total Tests:** {stats['total_tests']}",
            f"- **Passed:** {stats['total_passed']} ✅",
            f"- **Failed:** {stats['total_failed']} ❌",
            f"- **Success Rate:** {stats['success_rate']:.1f}%",
            f"- **Regression Status:** {'✅ PASSED' if stats['regression_passed'] else '❌ FAILED'}",
            "",
            "## Test Suite Results",
            ""
        ])
        
        # Add individual suite results
        for suite_result in summary['suite_results']:
            status = "✅ PASSED" if suite_result['success_rate'] >= 80 else "❌ FAILED"
            report_lines.extend([
                f"### {suite_result['suite_name']}",
                f"**Status:** {status}",
                f"**Duration:** {suite_result['duration_seconds']:.2f}s",
                f"**Tests:** {suite_result['total_tests']} total, {suite_result['passed_tests']} passed, {suite_result['failed_tests']} failed",
                f"**Success Rate:** {suite_result['success_rate']:.1f}%",
                ""
            ])
            
            if suite_result['errors']:
                report_lines.extend([
                    "**Errors:**",
                    ""
                ])
                for error in suite_result['errors'][:5]:  # Show first 5 errors
                    report_lines.append(f"- {error}")
                if len(suite_result['errors']) > 5:
                    report_lines.append(f"- ... and {len(suite_result['errors']) - 5} more errors")
                report_lines.append("")
        
        # Add configuration
        report_lines.extend([
            "## Test Configuration",
            "",
            "```json"
        ])
        report_lines.append(json.dumps(summary['test_config'], indent=2))
        report_lines.extend(["```", ""])
        
        # Add recommendations
        report_lines.extend([
            "## Recommendations",
            ""
        ])
        
        if stats['regression_passed']:
            report_lines.append("✅ All tests are passing within acceptable thresholds. The system is ready for deployment.")
        else:
            report_lines.append("❌ Some tests are failing below acceptable thresholds. Review and fix issues before deployment.")
            
            if stats['success_rate'] < 90:
                report_lines.append("- **Critical:** Success rate is below 90%. Immediate attention required.")
            elif stats['success_rate'] < 95:
                report_lines.append("- **Warning:** Success rate is below 95%. Consider investigating failing tests.")
        
        report = "\n".join(report_lines)
        
        # Write report to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Comprehensive test report written to: {output_file}")
        
        return report
    
    def run_regression_tests(self) -> bool:
        """Run regression tests and return pass/fail status."""
        logger.info("Running regression test suite...")
        
        summary = self.run_all_test_suites()
        
        # Generate report
        self.generate_comprehensive_report(summary)
        
        # Return regression status
        return summary['overall_statistics']['regression_passed']
    
    def run_ci_pipeline(self) -> int:
        """Run continuous integration pipeline and return exit code."""
        logger.info("Starting CI pipeline execution...")
        
        try:
            # Run all tests
            regression_passed = self.run_regression_tests()
            
            if regression_passed:
                logger.info("✅ CI Pipeline PASSED - All tests within acceptable thresholds")
                return 0
            else:
                logger.error("❌ CI Pipeline FAILED - Tests below acceptable thresholds")
                return 1
                
        except Exception as e:
            logger.error(f"❌ CI Pipeline CRASHED - {e}")
            return 2