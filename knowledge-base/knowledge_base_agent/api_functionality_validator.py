"""
API Functionality Validator

Enhanced validation for API endpoint functionality, response consistency,
and error handling patterns.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import requests
from urllib.parse import urljoin
import time

logger = logging.getLogger(__name__)


@dataclass
class FunctionalityTest:
    """Data structure for functionality test results."""
    endpoint: str
    method: str
    test_name: str
    status: str  # 'pass', 'fail', 'skip'
    message: str
    expected_status: Optional[int] = None
    actual_status: Optional[int] = None
    response_data: Optional[Dict] = None
    execution_time: Optional[float] = None


class APIFunctionalityValidator:
    """Validates API endpoint functionality and response patterns."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        
    def validate_endpoint_functionality(self, endpoints: List[Dict]) -> List[FunctionalityTest]:
        """Run comprehensive functionality tests on API endpoints."""
        results = []
        
        for endpoint in endpoints:
            if endpoint.get('is_deprecated'):
                continue  # Skip deprecated endpoints
                
            endpoint_tests = self._test_endpoint_functionality(endpoint)
            results.extend(endpoint_tests)
            
        return results
    
    def _test_endpoint_functionality(self, endpoint: Dict) -> List[FunctionalityTest]:
        """Test functionality for a specific endpoint."""
        tests = []
        rule = endpoint['rule']
        methods = endpoint['methods']
        
        for method in methods:
            # Test basic accessibility
            test = self._test_basic_accessibility(rule, method)
            tests.append(test)
            
            # Test response format consistency
            if test.status == 'pass':
                format_test = self._test_response_format(rule, method, test.response_data)
                tests.append(format_test)
                
                # Test error handling if applicable
                error_test = self._test_error_handling(rule, method)
                if error_test:
                    tests.append(error_test)
            
            # Test specific endpoint patterns
            pattern_tests = self._test_endpoint_patterns(rule, method, endpoint)
            tests.extend(pattern_tests)
            
        return tests
    
    def _test_basic_accessibility(self, rule: str, method: str) -> FunctionalityTest:
        """Test basic endpoint accessibility."""
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        start_time = time.time()
        
        try:
            kwargs = {'timeout': 10}
            
            if method in ['POST', 'PUT', 'PATCH']:
                kwargs['json'] = self._get_test_payload(rule, method)
            
            response = self.session.request(method, full_url, **kwargs)
            execution_time = time.time() - start_time
            
            # Parse response
            response_data = None
            try:
                response_data = response.json()
            except:
                pass
            
            # Determine test result
            if response.status_code < 500:
                status = 'pass'
                message = f"Accessible (HTTP {response.status_code})"
            else:
                status = 'fail'
                message = f"Server error (HTTP {response.status_code})"
                
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='basic_accessibility',
                status=status,
                message=message,
                actual_status=response.status_code,
                response_data=response_data,
                execution_time=execution_time
            )
            
        except requests.exceptions.ConnectionError:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='basic_accessibility',
                status='fail',
                message="Connection failed - server not running"
            )
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='basic_accessibility',
                status='fail',
                message=f"Request failed: {str(e)}"
            )
    
    def _test_response_format(self, rule: str, method: str, response_data: Optional[Dict]) -> FunctionalityTest:
        """Test response format consistency."""
        issues = []
        
        if response_data is None:
            # Check if this endpoint should return JSON
            if not any(pattern in rule for pattern in ['/static/', '/media/', '/v2/page/']):
                issues.append("Expected JSON response but got non-JSON")
        else:
            # Validate JSON response structure
            if isinstance(response_data, dict):
                # Check for consistent error format
                if 'error' in response_data:
                    if 'success' not in response_data:
                        issues.append("Error response missing 'success' field")
                    elif response_data.get('success') is not False:
                        issues.append("Error response has success=true")
                
                # Check for consistent success format
                if 'success' in response_data:
                    if not isinstance(response_data['success'], bool):
                        issues.append("'success' field should be boolean")
        
        if issues:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='response_format',
                status='fail',
                message=f"Format issues: {'; '.join(issues)}"
            )
        else:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='response_format',
                status='pass',
                message="Response format is consistent"
            )
    
    def _test_error_handling(self, rule: str, method: str) -> Optional[FunctionalityTest]:
        """Test error handling patterns."""
        # Test with invalid data for POST/PUT endpoints
        if method not in ['POST', 'PUT', 'PATCH']:
            return None
            
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            # Send invalid JSON
            response = self.session.request(
                method, 
                full_url, 
                json={'invalid': 'data', 'test': True},
                timeout=5
            )
            
            # Check if error is handled properly
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and 'error' in error_data:
                        return FunctionalityTest(
                            endpoint=rule,
                            method=method,
                            test_name='error_handling',
                            status='pass',
                            message="Proper error response format",
                            actual_status=response.status_code
                        )
                    else:
                        return FunctionalityTest(
                            endpoint=rule,
                            method=method,
                            test_name='error_handling',
                            status='fail',
                            message="Error response missing proper format"
                        )
                except:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='error_handling',
                        status='fail',
                        message="Error response is not valid JSON"
                    )
            else:
                return FunctionalityTest(
                    endpoint=rule,
                    method=method,
                    test_name='error_handling',
                    status='fail',
                    message="Invalid data accepted without error"
                )
                
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='error_handling',
                status='fail',
                message=f"Error test failed: {str(e)}"
            )
    
    def _test_endpoint_patterns(self, rule: str, method: str, endpoint: Dict) -> List[FunctionalityTest]:
        """Test specific patterns based on endpoint category."""
        tests = []
        category = endpoint.get('category', '')
        
        # Agent Management endpoints
        if 'Agent Management' in category:
            if 'status' in rule and method == 'GET':
                test = self._test_status_endpoint(rule, method)
                tests.append(test)
            elif 'start' in rule and method == 'POST':
                test = self._test_agent_start_endpoint(rule, method)
                tests.append(test)
        
        # Chat endpoints
        elif 'Chat' in category:
            if method == 'POST' and '/chat' in rule and '<' not in rule:
                test = self._test_chat_endpoint(rule, method)
                tests.append(test)
        
        # Configuration endpoints
        elif 'Configuration' in category:
            if 'preferences' in rule:
                if method == 'GET':
                    test = self._test_preferences_get(rule, method)
                    tests.append(test)
                elif method == 'POST':
                    test = self._test_preferences_post(rule, method)
                    tests.append(test)
        
        return tests
    
    def _test_status_endpoint(self, rule: str, method: str) -> FunctionalityTest:
        """Test status endpoint specific functionality."""
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            response = self.session.get(full_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for expected status fields
                expected_fields = ['is_running', 'current_phase_message']
                missing_fields = [field for field in expected_fields if field not in data]
                
                if missing_fields:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='status_fields',
                        status='fail',
                        message=f"Missing status fields: {', '.join(missing_fields)}"
                    )
                else:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='status_fields',
                        status='pass',
                        message="Status endpoint has required fields"
                    )
            else:
                return FunctionalityTest(
                    endpoint=rule,
                    method=method,
                    test_name='status_fields',
                    status='fail',
                    message=f"Status endpoint returned {response.status_code}"
                )
                
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='status_fields',
                status='fail',
                message=f"Status test failed: {str(e)}"
            )
    
    def _test_agent_start_endpoint(self, rule: str, method: str) -> FunctionalityTest:
        """Test agent start endpoint functionality."""
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            # Test with minimal valid preferences
            payload = {
                'preferences': {
                    'run_mode': 'test',
                    'skip_fetch_bookmarks': True,
                    'skip_process_content': True
                }
            }
            
            response = self.session.post(full_url, json=payload, timeout=10)
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Check for expected response fields
                if 'task_id' in data and 'success' in data:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='agent_start',
                        status='pass',
                        message="Agent start endpoint works correctly"
                    )
                else:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='agent_start',
                        status='fail',
                        message="Agent start response missing required fields"
                    )
            else:
                return FunctionalityTest(
                    endpoint=rule,
                    method=method,
                    test_name='agent_start',
                    status='fail',
                    message=f"Agent start returned {response.status_code}"
                )
                
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='agent_start',
                status='fail',
                message=f"Agent start test failed: {str(e)}"
            )
    
    def _test_chat_endpoint(self, rule: str, method: str) -> FunctionalityTest:
        """Test chat endpoint functionality."""
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            payload = {'message': 'Hello, this is a test message'}
            response = self.session.post(full_url, json=payload, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for expected chat response fields
                if 'response' in data:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='chat_functionality',
                        status='pass',
                        message="Chat endpoint responds correctly"
                    )
                elif 'error' in data:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='chat_functionality',
                        status='fail',
                        message=f"Chat endpoint error: {data['error']}"
                    )
                else:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='chat_functionality',
                        status='fail',
                        message="Chat response missing 'response' field"
                    )
            else:
                return FunctionalityTest(
                    endpoint=rule,
                    method=method,
                    test_name='chat_functionality',
                    status='fail',
                    message=f"Chat endpoint returned {response.status_code}"
                )
                
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='chat_functionality',
                status='fail',
                message=f"Chat test failed: {str(e)}"
            )
    
    def _test_preferences_get(self, rule: str, method: str) -> FunctionalityTest:
        """Test preferences GET endpoint."""
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            response = self.session.get(full_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for expected preference fields
                expected_fields = ['run_mode', 'skip_fetch_bookmarks']
                present_fields = [field for field in expected_fields if field in data]
                
                if present_fields:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='preferences_structure',
                        status='pass',
                        message="Preferences endpoint has expected structure"
                    )
                else:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='preferences_structure',
                        status='fail',
                        message="Preferences response missing expected fields"
                    )
            else:
                return FunctionalityTest(
                    endpoint=rule,
                    method=method,
                    test_name='preferences_structure',
                    status='fail',
                    message=f"Preferences GET returned {response.status_code}"
                )
                
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='preferences_structure',
                status='fail',
                message=f"Preferences GET test failed: {str(e)}"
            )
    
    def _test_preferences_post(self, rule: str, method: str) -> FunctionalityTest:
        """Test preferences POST endpoint."""
        test_url = self._build_test_url(rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            payload = {
                'run_mode': 'test',
                'skip_fetch_bookmarks': True
            }
            
            response = self.session.post(full_url, json=payload, timeout=5)
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                if 'status' in data or 'success' in data:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='preferences_save',
                        status='pass',
                        message="Preferences save works correctly"
                    )
                else:
                    return FunctionalityTest(
                        endpoint=rule,
                        method=method,
                        test_name='preferences_save',
                        status='fail',
                        message="Preferences save response missing status"
                    )
            else:
                return FunctionalityTest(
                    endpoint=rule,
                    method=method,
                    test_name='preferences_save',
                    status='fail',
                    message=f"Preferences POST returned {response.status_code}"
                )
                
        except Exception as e:
            return FunctionalityTest(
                endpoint=rule,
                method=method,
                test_name='preferences_save',
                status='fail',
                message=f"Preferences POST test failed: {str(e)}"
            )
    
    def _build_test_url(self, rule: str) -> str:
        """Build a test URL by replacing path parameters with dummy values."""
        import re
        test_url = rule
        test_url = re.sub(r'<int:(\w+)>', '1', test_url)
        test_url = re.sub(r'<(\w+)>', 'test', test_url)
        test_url = re.sub(r'<string:(\w+)>', 'test', test_url)
        test_url = re.sub(r'<path:(\w+)>', 'test/path', test_url)
        return test_url
    
    def _get_test_payload(self, rule: str, method: str) -> Dict:
        """Get appropriate test payload for endpoint."""
        # Default empty payload
        payload = {}
        
        # Specific payloads for known endpoints
        if 'agent/start' in rule:
            payload = {
                'preferences': {
                    'run_mode': 'test',
                    'skip_fetch_bookmarks': True
                }
            }
        elif 'chat' in rule:
            payload = {'message': 'test message'}
        elif 'preferences' in rule:
            payload = {'run_mode': 'test'}
        elif 'schedule' in rule:
            payload = {'schedule': 'manual'}
        
        return payload


def run_functionality_validation(endpoints: List[Dict], base_url: str = "http://localhost:5000") -> Dict[str, Any]:
    """Run comprehensive functionality validation."""
    logger.info("Starting API functionality validation...")
    
    validator = APIFunctionalityValidator(base_url)
    test_results = validator.validate_endpoint_functionality(endpoints)
    
    # Compile statistics
    total_tests = len(test_results)
    passed_tests = len([t for t in test_results if t.status == 'pass'])
    failed_tests = len([t for t in test_results if t.status == 'fail'])
    skipped_tests = len([t for t in test_results if t.status == 'skip'])
    
    # Group by endpoint
    by_endpoint = {}
    for test in test_results:
        key = f"{test.method} {test.endpoint}"
        if key not in by_endpoint:
            by_endpoint[key] = []
        by_endpoint[key].append(test)
    
    results = {
        'statistics': {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'skipped': skipped_tests,
            'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        },
        'test_results': [asdict(t) for t in test_results],
        'by_endpoint': {k: [asdict(t) for t in v] for k, v in by_endpoint.items()},
        'failed_tests': [asdict(t) for t in test_results if t.status == 'fail']
    }
    
    logger.info(f"Functionality validation completed. Pass rate: {results['statistics']['pass_rate']:.1f}%")
    
    return results