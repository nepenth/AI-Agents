"""
Prompt Comparison Testing Framework

This module provides comprehensive testing to compare original vs JSON prompt outputs
to ensure functional equivalence and validate the JSON prompt system.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
import difflib
import re

# Import original prompts
from .prompts import LLMPrompts, ReasoningPrompts

# Import JSON prompt system
from .json_prompt_manager import JsonPromptManager, JsonPromptManagerError
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of comparing original vs JSON prompt output."""
    test_name: str
    original_output: str
    json_output: str
    identical: bool
    similarity_score: float
    differences: List[str]
    error: Optional[str] = None


@dataclass
class TestCase:
    """Test case definition for prompt comparison."""
    name: str
    prompt_method: str
    json_prompt_id: str
    model_type: str
    parameters: Dict[str, Any]
    description: str
    expected_differences: List[str] = None  # Known acceptable differences


class PromptComparisonTester:
    """
    Framework for comparing original and JSON prompt outputs.
    
    Provides comprehensive testing to ensure functional equivalence
    between the original prompt system and the new JSON-based system.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the comparison tester."""
        self.config = config or Config.from_env()
        self.json_manager = JsonPromptManager(config)
        self.results: List[ComparisonResult] = []
        
        # Test cases for different prompt types
        self.test_cases = self._define_test_cases()
        
        logger.info(f"PromptComparisonTester initialized with {len(self.test_cases)} test cases")
    
    def _define_test_cases(self) -> List[TestCase]:
        """Define comprehensive test cases for all prompt types."""
        return [
            # Categorization prompts
            TestCase(
                name="categorization_single_tweet",
                prompt_method="get_categorization_prompt_standard",
                json_prompt_id="categorization_standard",
                model_type="standard",
                parameters={
                    "context_content": "Docker multi-stage builds can reduce image size by 80%. Key techniques include layer caching and minimal base images.",
                    "formatted_existing_categories": "containerization, devops_automation, cloud_architecture",
                    "is_thread": False
                },
                description="Test categorization of single tweet content"
            ),
            TestCase(
                name="categorization_thread_content",
                prompt_method="get_categorization_prompt_standard", 
                json_prompt_id="categorization_standard",
                model_type="standard",
                parameters={
                    "context_content": "Thread about Kubernetes networking: 1) Pod-to-pod communication 2) Service discovery 3) Ingress controllers",
                    "formatted_existing_categories": "kubernetes, networking, container_orchestration",
                    "is_thread": True
                },
                description="Test categorization of thread content"
            ),
            
            # Chat prompts
            TestCase(
                name="chat_standard_prompt",
                prompt_method="get_chat_prompt",
                json_prompt_id="chat_standard",
                model_type="standard",
                parameters={},
                description="Test standard chat system prompt"
            ),
            TestCase(
                name="chat_synthesis_aware",
                prompt_method="get_synthesis_aware_chat_prompt",
                json_prompt_id="chat_synthesis_aware",
                model_type="standard",
                parameters={},
                description="Test synthesis-aware chat prompt"
            ),
            TestCase(
                name="chat_contextual_explanation",
                prompt_method="get_contextual_chat_response_prompt",
                json_prompt_id="chat_contextual_response",
                model_type="standard",
                parameters={"query_type": "explanation"},
                description="Test contextual chat response for explanation queries"
            ),
            TestCase(
                name="chat_contextual_implementation",
                prompt_method="get_contextual_chat_response_prompt",
                json_prompt_id="chat_contextual_response",
                model_type="standard",
                parameters={"query_type": "implementation"},
                description="Test contextual chat response for implementation queries"
            ),
            
            # KB Item Generation
            TestCase(
                name="kb_item_generation_single_tweet",
                prompt_method="get_kb_item_generation_prompt_standard",
                json_prompt_id="kb_item_generation_standard",
                model_type="standard",
                parameters={
                    "context_data": {
                        "tweet_text": "PostgreSQL EXPLAIN ANALYZE shows query execution time and actual rows. Essential for performance tuning.",
                        "main_category": "database_internals",
                        "sub_category": "postgresql_optimization",
                        "item_name": "postgres_explain_analyze",
                        "all_urls": ["https://www.postgresql.org/docs/current/sql-explain.html"],
                        "all_media_descriptions": ["Screenshot of EXPLAIN ANALYZE output"]
                    }
                },
                description="Test KB item generation from single tweet"
            ),
            TestCase(
                name="kb_item_generation_thread",
                prompt_method="get_kb_item_generation_prompt_standard",
                json_prompt_id="kb_item_generation_standard",
                model_type="standard",
                parameters={
                    "context_data": {
                        "tweet_segments": [
                            "React useCallback optimization patterns",
                            "Avoid recreating functions on every render",
                            "Dependency array best practices"
                        ],
                        "main_category": "frontend_frameworks",
                        "sub_category": "react_optimization",
                        "item_name": "react_usecallback_patterns",
                        "all_urls": [],
                        "all_media_descriptions": []
                    }
                },
                description="Test KB item generation from tweet thread"
            ),
            
            # Synthesis Generation
            TestCase(
                name="synthesis_comprehensive",
                prompt_method="get_synthesis_generation_prompt_standard",
                json_prompt_id="synthesis_generation_standard",
                model_type="standard",
                parameters={
                    "main_category": "concurrency_patterns",
                    "sub_category": "thread_synchronization_java",
                    "kb_items_content": "Item 1: AtomicLong vs synchronized blocks...\nItem 2: ReentrantLock usage patterns...",
                    "synthesis_mode": "comprehensive"
                },
                description="Test comprehensive synthesis generation"
            ),
            TestCase(
                name="synthesis_technical_deep_dive",
                prompt_method="get_synthesis_generation_prompt_standard",
                json_prompt_id="synthesis_generation_standard",
                model_type="standard",
                parameters={
                    "main_category": "api_design_patterns",
                    "sub_category": "rest_api_security",
                    "kb_items_content": "Item 1: JWT authentication...\nItem 2: OAuth2 flows...",
                    "synthesis_mode": "technical_deep_dive"
                },
                description="Test technical deep dive synthesis generation"
            ),
            
            # README Generation
            TestCase(
                name="readme_introduction",
                prompt_method="get_readme_introduction_prompt_standard",
                json_prompt_id="readme_introduction_standard",
                model_type="standard",
                parameters={
                    "kb_stats": {
                        "total_items": 150,
                        "total_synthesis": 25,
                        "total_combined": 175,
                        "total_main_cats": 8,
                        "total_subcats": 32,
                        "total_media": 45
                    },
                    "category_list": "Backend Frameworks, Cloud Architecture, DevOps Automation, Database Internals"
                },
                description="Test README introduction generation"
            ),
            TestCase(
                name="readme_category_description",
                prompt_method="get_readme_category_description_prompt_standard",
                json_prompt_id="readme_category_description_standard",
                model_type="standard",
                parameters={
                    "main_display": "Backend Frameworks",
                    "total_cat_items": 25,
                    "active_subcats": ["spring_boot", "express_js", "django_patterns"]
                },
                description="Test README category description generation"
            ),
            
            # Short Name Generation
            TestCase(
                name="short_name_generation",
                prompt_method="get_short_name_generation_prompt",
                json_prompt_id="short_name_generation",
                model_type="standard",
                parameters={},
                description="Test short name generation for categories"
            ),
            
            # Reasoning Prompts
            TestCase(
                name="reasoning_categorization",
                prompt_method="get_categorization_prompt",
                json_prompt_id="categorization_reasoning",
                model_type="reasoning",
                parameters={
                    "context_content": "Advanced Kubernetes networking with Istio service mesh",
                    "formatted_existing_categories": "kubernetes, service_mesh, networking",
                    "is_thread": False
                },
                description="Test reasoning-based categorization"
            ),
            TestCase(
                name="reasoning_kb_item",
                prompt_method="get_kb_item_generation_prompt",
                json_prompt_id="kb_item_generation_reasoning",
                model_type="reasoning",
                parameters={
                    "tweet_text": "Redis clustering and high availability patterns",
                    "categories": {
                        "main_category": "database_systems",
                        "sub_category": "redis_clustering",
                        "item_name": "redis_ha_patterns"
                    },
                    "media_descriptions": []
                },
                description="Test reasoning-based KB item generation"
            ),
            TestCase(
                name="reasoning_synthesis",
                prompt_method="get_synthesis_generation_prompt",
                json_prompt_id="synthesis_generation_reasoning",
                model_type="reasoning",
                parameters={
                    "main_category": "microservices_architecture",
                    "sub_category": "service_communication",
                    "kb_items_content": "Item 1: gRPC vs REST...\nItem 2: Message queues...",
                    "synthesis_mode": "comprehensive"
                },
                description="Test reasoning-based synthesis generation"
            )
        ]
    
    def run_comparison_test(self, test_case: TestCase) -> ComparisonResult:
        """Run a single comparison test."""
        logger.info(f"Running test: {test_case.name}")
        
        try:
            # Get original prompt output
            original_output = self._get_original_output(test_case)
            
            # Get JSON prompt output
            json_output = self._get_json_output(test_case)
            
            # Compare outputs
            comparison = self._compare_outputs(original_output, json_output, test_case)
            
            return ComparisonResult(
                test_name=test_case.name,
                original_output=original_output,
                json_output=json_output,
                identical=comparison['identical'],
                similarity_score=comparison['similarity_score'],
                differences=comparison['differences']
            )
            
        except Exception as e:
            logger.error(f"Test {test_case.name} failed: {e}")
            return ComparisonResult(
                test_name=test_case.name,
                original_output="",
                json_output="",
                identical=False,
                similarity_score=0.0,
                differences=[],
                error=str(e)
            )
    
    def _get_original_output(self, test_case: TestCase) -> str:
        """Get output from original prompt system."""
        if test_case.model_type == "standard":
            method = getattr(LLMPrompts, test_case.prompt_method)
        else:  # reasoning
            method = getattr(ReasoningPrompts, test_case.prompt_method)
        
        # Call the method with parameters
        if test_case.parameters:
            # Handle different parameter patterns
            if test_case.prompt_method == "get_categorization_prompt_standard":
                return method(
                    test_case.parameters["context_content"],
                    test_case.parameters["formatted_existing_categories"],
                    test_case.parameters.get("is_thread", False)
                )
            elif test_case.prompt_method == "get_kb_item_generation_prompt_standard":
                return method(test_case.parameters["context_data"])
            elif test_case.prompt_method == "get_synthesis_generation_prompt_standard":
                return method(
                    test_case.parameters["main_category"],
                    test_case.parameters["sub_category"],
                    test_case.parameters["kb_items_content"],
                    test_case.parameters.get("synthesis_mode", "comprehensive")
                )
            elif test_case.prompt_method == "get_readme_introduction_prompt_standard":
                return method(
                    test_case.parameters["kb_stats"],
                    test_case.parameters["category_list"]
                )
            elif test_case.prompt_method == "get_readme_category_description_prompt_standard":
                return method(
                    test_case.parameters["main_display"],
                    test_case.parameters["total_cat_items"],
                    test_case.parameters["active_subcats"]
                )
            elif test_case.prompt_method == "get_contextual_chat_response_prompt":
                return method(test_case.parameters.get("query_type", "general"))
            elif test_case.prompt_method in ["get_categorization_prompt", "get_kb_item_generation_prompt", "get_synthesis_generation_prompt"]:
                # Reasoning prompts - return the content part
                if test_case.prompt_method == "get_categorization_prompt":
                    result = method(
                        test_case.parameters["context_content"],
                        test_case.parameters["formatted_existing_categories"],
                        test_case.parameters.get("is_thread", False)
                    )
                elif test_case.prompt_method == "get_kb_item_generation_prompt":
                    result = method(
                        test_case.parameters["tweet_text"],
                        test_case.parameters["categories"],
                        test_case.parameters.get("media_descriptions", [])
                    )
                elif test_case.prompt_method == "get_synthesis_generation_prompt":
                    result = method(
                        test_case.parameters["main_category"],
                        test_case.parameters["sub_category"],
                        test_case.parameters["kb_items_content"],
                        test_case.parameters.get("synthesis_mode", "comprehensive")
                    )
                
                # For reasoning prompts, return the user message content
                return result.get("content", str(result))
            else:
                # Try to call with all parameters as kwargs
                return method(**test_case.parameters)
        else:
            return method()
    
    def _get_json_output(self, test_case: TestCase) -> str:
        """Get output from JSON prompt system."""
        result = self.json_manager.render_prompt(
            test_case.json_prompt_id,
            test_case.parameters,
            test_case.model_type
        )
        
        # For reasoning models, extract the content from the message structure
        if test_case.model_type == "reasoning" and isinstance(result.content, dict):
            return result.content.get("content", str(result.content))
        
        return result.content
    
    def _compare_outputs(self, original: str, json_output: str, test_case: TestCase) -> Dict[str, Any]:
        """Compare two prompt outputs and return comparison metrics."""
        # Normalize whitespace for comparison
        original_normalized = re.sub(r'\s+', ' ', original.strip())
        json_normalized = re.sub(r'\s+', ' ', json_output.strip())
        
        # Check if identical
        identical = original_normalized == json_normalized
        
        # Calculate similarity score using difflib
        similarity_score = difflib.SequenceMatcher(None, original_normalized, json_normalized).ratio()
        
        # Find differences
        differences = []
        if not identical:
            diff = list(difflib.unified_diff(
                original_normalized.splitlines(keepends=True),
                json_normalized.splitlines(keepends=True),
                fromfile='original',
                tofile='json',
                lineterm=''
            ))
            differences = [line.strip() for line in diff if line.startswith(('+', '-', '?'))]
        
        return {
            'identical': identical,
            'similarity_score': similarity_score,
            'differences': differences
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all comparison tests and return comprehensive results."""
        logger.info(f"Starting comprehensive prompt comparison tests ({len(self.test_cases)} tests)")
        
        self.results = []
        passed = 0
        failed = 0
        high_similarity = 0  # >= 95% similarity
        
        for test_case in self.test_cases:
            result = self.run_comparison_test(test_case)
            self.results.append(result)
            
            if result.error:
                failed += 1
                logger.error(f"❌ {test_case.name}: {result.error}")
            elif result.identical:
                passed += 1
                logger.info(f"✅ {test_case.name}: IDENTICAL")
            elif result.similarity_score >= 0.95:
                high_similarity += 1
                logger.info(f"🔶 {test_case.name}: HIGH SIMILARITY ({result.similarity_score:.1%})")
            else:
                failed += 1
                logger.warning(f"⚠️  {test_case.name}: LOW SIMILARITY ({result.similarity_score:.1%})")
        
        # Generate summary
        total_tests = len(self.test_cases)
        summary = {
            'total_tests': total_tests,
            'identical': passed,
            'high_similarity': high_similarity,
            'failed': failed,
            'success_rate': ((passed + high_similarity) / total_tests) * 100,
            'average_similarity': sum(r.similarity_score for r in self.results if not r.error) / max(1, total_tests - failed),
            'test_results': self.results
        }
        
        logger.info(f"Test Summary: {passed} identical, {high_similarity} high similarity, {failed} failed")
        logger.info(f"Success Rate: {summary['success_rate']:.1f}%")
        logger.info(f"Average Similarity: {summary['average_similarity']:.1%}")
        
        return summary
    
    def generate_report(self, output_file: Optional[Path] = None) -> str:
        """Generate a detailed comparison report."""
        if not self.results:
            return "No test results available. Run tests first."
        
        report_lines = [
            "# Prompt Comparison Test Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Total Tests: {len(self.results)}",
            "",
            "## Summary",
        ]
        
        # Calculate summary stats
        identical = sum(1 for r in self.results if r.identical and not r.error)
        high_similarity = sum(1 for r in self.results if not r.identical and not r.error and r.similarity_score >= 0.95)
        failed = sum(1 for r in self.results if r.error)
        
        report_lines.extend([
            f"- ✅ Identical: {identical}",
            f"- 🔶 High Similarity (≥95%): {high_similarity}",
            f"- ❌ Failed: {failed}",
            f"- 📈 Success Rate: {((identical + high_similarity) / len(self.results)) * 100:.1f}%",
            "",
            "## Detailed Results",
            ""
        ])
        
        # Add detailed results
        for result in self.results:
            report_lines.extend([
                f"### {result.test_name}",
                ""
            ])
            
            if result.error:
                report_lines.extend([
                    f"**Status:** ❌ ERROR",
                    f"**Error:** {result.error}",
                    ""
                ])
            elif result.identical:
                report_lines.extend([
                    f"**Status:** ✅ IDENTICAL",
                    f"**Similarity:** 100%",
                    ""
                ])
            else:
                status = "🔶 HIGH SIMILARITY" if result.similarity_score >= 0.95 else "⚠️ LOW SIMILARITY"
                report_lines.extend([
                    f"**Status:** {status}",
                    f"**Similarity:** {result.similarity_score:.1%}",
                    ""
                ])
                
                if result.differences:
                    report_lines.extend([
                        "**Key Differences:**",
                        "```diff"
                    ])
                    report_lines.extend(result.differences[:10])  # Limit to first 10 differences
                    if len(result.differences) > 10:
                        report_lines.append(f"... and {len(result.differences) - 10} more differences")
                    report_lines.extend(["```", ""])
        
        report = "\n".join(report_lines)
        
        # Write to file if specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Report written to: {output_file}")
        
        return report
    
    def get_failing_tests(self) -> List[ComparisonResult]:
        """Get list of tests that failed or have low similarity."""
        return [
            result for result in self.results
            if result.error or (not result.identical and result.similarity_score < 0.95)
        ]
    
    def get_test_by_name(self, test_name: str) -> Optional[ComparisonResult]:
        """Get a specific test result by name."""
        for result in self.results:
            if result.test_name == test_name:
                return result
        return None