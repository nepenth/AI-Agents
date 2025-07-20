"""
API Endpoint Discovery and Validation Tool

This module provides comprehensive validation and discovery of Flask API endpoints
for the Knowledge Base Agent system.
"""

import inspect
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from flask import Flask
from werkzeug.routing import Rule
import requests
from urllib.parse import urljoin
import re

logger = logging.getLogger(__name__)


@dataclass
class EndpointInfo:
    """Data structure for endpoint information."""
    rule: str
    methods: List[str]
    endpoint: str
    function_name: str
    module: str
    docstring: Optional[str]
    parameters: List[str]
    url_variables: List[str]
    is_deprecated: bool = False
    category: Optional[str] = None


@dataclass
class ValidationResult:
    """Data structure for validation results."""
    endpoint: str
    method: str
    status: str  # 'success', 'error', 'warning'
    message: str
    response_code: Optional[int] = None
    response_data: Optional[Dict] = None
    error_details: Optional[str] = None


class APIEndpointDiscovery:
    """Discovers and analyzes Flask API endpoints."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.endpoints: List[EndpointInfo] = []
        
    def discover_endpoints(self) -> List[EndpointInfo]:
        """Discover all Flask routes and extract their metadata."""
        logger.info("Starting API endpoint discovery...")
        
        endpoints = []
        
        # Get all URL rules from the Flask app
        for rule in self.app.url_map.iter_rules():
            try:
                endpoint_info = self._analyze_rule(rule)
                if endpoint_info:
                    endpoints.append(endpoint_info)
            except Exception as e:
                logger.error(f"Error analyzing rule {rule}: {e}")
                
        self.endpoints = endpoints
        logger.info(f"Discovered {len(endpoints)} API endpoints")
        return endpoints
    
    def _analyze_rule(self, rule: Rule) -> Optional[EndpointInfo]:
        """Analyze a single Flask rule and extract information."""
        try:
            # Get the view function
            view_func = self.app.view_functions.get(rule.endpoint)
            if not view_func:
                return None
                
            # Extract function information
            function_name = view_func.__name__
            module = view_func.__module__
            docstring = inspect.getdoc(view_func)
            
            # Get function parameters
            sig = inspect.signature(view_func)
            parameters = list(sig.parameters.keys())
            
            # Extract URL variables
            url_variables = list(rule.arguments) if rule.arguments else []
            
            # Determine if deprecated
            is_deprecated = self._is_deprecated(view_func, docstring)
            
            # Categorize endpoint
            category = self._categorize_endpoint(rule.rule)
            
            return EndpointInfo(
                rule=rule.rule,
                methods=list(rule.methods - {'HEAD', 'OPTIONS'}),  # Remove automatic methods
                endpoint=rule.endpoint,
                function_name=function_name,
                module=module,
                docstring=docstring,
                parameters=parameters,
                url_variables=url_variables,
                is_deprecated=is_deprecated,
                category=category
            )
            
        except Exception as e:
            logger.error(f"Error analyzing rule {rule.rule}: {e}")
            return None
    
    def _is_deprecated(self, view_func, docstring: Optional[str]) -> bool:
        """Check if an endpoint is deprecated."""
        if docstring and 'DEPRECATED' in docstring.upper():
            return True
            
        # Check for deprecated decorators or markers
        if hasattr(view_func, '__name__'):
            if 'legacy' in view_func.__name__.lower():
                return True
                
        return False
    
    def _categorize_endpoint(self, rule: str) -> str:
        """Categorize endpoint based on URL pattern."""
        if rule.startswith('/api/v2/agent'):
            return 'Agent Management (V2)'
        elif rule.startswith('/api/v2/celery'):
            return 'Celery Management (V2)'
        elif rule.startswith('/api/agent'):
            return 'Agent Management'
        elif rule.startswith('/api/chat'):
            return 'Chat & AI'
        elif rule.startswith('/api/utilities'):
            return 'System Utilities'
        elif rule.startswith('/api/logs'):
            return 'Logging'
        elif rule.startswith('/api/preferences'):
            return 'Configuration'
        elif rule.startswith('/api/environment'):
            return 'Environment'
        elif rule.startswith('/api/schedules'):
            return 'Scheduling'
        elif rule.startswith('/api/synthesis'):
            return 'Knowledge Base'
        elif rule.startswith('/api/gpu'):
            return 'Hardware Monitoring'
        elif rule.startswith('/api/'):
            return 'API'
        elif rule.startswith('/v2/'):
            return 'Web UI (V2)'
        else:
            return 'Web UI'
    
    def validate_route_conflicts(self) -> List[ValidationResult]:
        """Check for route conflicts and overlapping patterns."""
        results = []
        
        # Group routes by pattern similarity
        route_groups = {}
        for endpoint in self.endpoints:
            # Create a pattern key by replacing variables with placeholders
            pattern_key = re.sub(r'<[^>]+>', '<var>', endpoint.rule)
            if pattern_key not in route_groups:
                route_groups[pattern_key] = []
            route_groups[pattern_key].append(endpoint)
        
        # Check for conflicts within groups
        for pattern, endpoints in route_groups.items():
            if len(endpoints) > 1:
                # Check if they have overlapping methods
                method_conflicts = self._check_method_conflicts(endpoints)
                if method_conflicts:
                    for conflict in method_conflicts:
                        results.append(ValidationResult(
                            endpoint=pattern,
                            method=conflict['method'],
                            status='warning',
                            message=f"Potential route conflict: {conflict['message']}"
                        ))
        
        return results
    
    def _check_method_conflicts(self, endpoints: List[EndpointInfo]) -> List[Dict]:
        """Check for HTTP method conflicts between endpoints."""
        conflicts = []
        method_map = {}
        
        for endpoint in endpoints:
            for method in endpoint.methods:
                if method in method_map:
                    conflicts.append({
                        'method': method,
                        'message': f"Method {method} defined in both {endpoint.function_name} and {method_map[method].function_name}"
                    })
                else:
                    method_map[method] = endpoint
                    
        return conflicts
    
    def generate_endpoint_summary(self) -> Dict[str, Any]:
        """Generate a summary of discovered endpoints."""
        if not self.endpoints:
            self.discover_endpoints()
            
        # Group by category
        by_category = {}
        deprecated_count = 0
        
        for endpoint in self.endpoints:
            category = endpoint.category or 'Uncategorized'
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(endpoint)
            
            if endpoint.is_deprecated:
                deprecated_count += 1
        
        # Calculate statistics
        total_endpoints = len(self.endpoints)
        total_methods = sum(len(ep.methods) for ep in self.endpoints)
        
        return {
            'total_endpoints': total_endpoints,
            'total_methods': total_methods,
            'deprecated_endpoints': deprecated_count,
            'categories': {cat: len(eps) for cat, eps in by_category.items()},
            'by_category': {cat: [asdict(ep) for ep in eps] for cat, eps in by_category.items()}
        }


class APIEndpointValidator:
    """Validates API endpoint functionality and responses."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        
    def validate_endpoint_accessibility(self, endpoints: List[EndpointInfo]) -> List[ValidationResult]:
        """Test if endpoints are accessible and return expected responses."""
        results = []
        
        for endpoint in endpoints:
            for method in endpoint.methods:
                try:
                    result = self._test_endpoint_method(endpoint, method)
                    results.append(result)
                except Exception as e:
                    results.append(ValidationResult(
                        endpoint=endpoint.rule,
                        method=method,
                        status='error',
                        message=f"Failed to test endpoint: {str(e)}",
                        error_details=str(e)
                    ))
        
        return results
    
    def _test_endpoint_method(self, endpoint: EndpointInfo, method: str) -> ValidationResult:
        """Test a specific endpoint method."""
        # Build URL with dummy values for path parameters
        test_url = self._build_test_url(endpoint.rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            # Prepare request based on method
            kwargs = {'timeout': 10}
            
            if method in ['POST', 'PUT', 'PATCH']:
                kwargs['json'] = {}  # Empty JSON body for testing
                kwargs['headers'] = {'Content-Type': 'application/json'}
            
            # Make request
            response = self.session.request(method, full_url, **kwargs)
            
            # Analyze response
            status = 'success' if response.status_code < 500 else 'error'
            if response.status_code == 404:
                status = 'warning'
                
            message = f"HTTP {response.status_code}"
            
            # Try to parse JSON response
            response_data = None
            try:
                response_data = response.json()
            except:
                pass
                
            return ValidationResult(
                endpoint=endpoint.rule,
                method=method,
                status=status,
                message=message,
                response_code=response.status_code,
                response_data=response_data
            )
            
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                endpoint=endpoint.rule,
                method=method,
                status='error',
                message="Connection failed - server not running",
                error_details="Could not connect to server"
            )
        except Exception as e:
            return ValidationResult(
                endpoint=endpoint.rule,
                method=method,
                status='error',
                message=f"Request failed: {str(e)}",
                error_details=str(e)
            )
    
    def _build_test_url(self, rule: str) -> str:
        """Build a test URL by replacing path parameters with dummy values."""
        # Replace common path parameters with test values
        test_url = rule
        test_url = re.sub(r'<int:(\w+)>', '1', test_url)
        test_url = re.sub(r'<(\w+)>', 'test', test_url)
        test_url = re.sub(r'<string:(\w+)>', 'test', test_url)
        test_url = re.sub(r'<path:(\w+)>', 'test/path', test_url)
        
        return test_url
    
    def validate_response_formats(self, endpoints: List[EndpointInfo]) -> List[ValidationResult]:
        """Validate that endpoints return consistent response formats."""
        results = []
        
        for endpoint in endpoints:
            if endpoint.is_deprecated:
                continue  # Skip deprecated endpoints
                
            for method in endpoint.methods:
                if method in ['GET', 'POST']:  # Focus on main methods
                    result = self._validate_response_format(endpoint, method)
                    if result:
                        results.append(result)
        
        return results
    
    def _validate_response_format(self, endpoint: EndpointInfo, method: str) -> Optional[ValidationResult]:
        """Validate response format for a specific endpoint method."""
        test_url = self._build_test_url(endpoint.rule)
        full_url = urljoin(self.base_url, test_url)
        
        try:
            kwargs = {'timeout': 5}
            if method == 'POST':
                kwargs['json'] = {}
                kwargs['headers'] = {'Content-Type': 'application/json'}
            
            response = self.session.request(method, full_url, **kwargs)
            
            # Check if response is JSON
            try:
                data = response.json()
                
                # Validate common response patterns
                issues = []
                
                # Check for consistent error format
                if response.status_code >= 400:
                    if not isinstance(data, dict) or 'error' not in data:
                        issues.append("Error responses should include 'error' field")
                
                # Check for success format
                if response.status_code < 400:
                    if isinstance(data, dict) and 'success' in data:
                        if data['success'] is False and response.status_code < 400:
                            issues.append("Success=false with 2xx status code")
                
                if issues:
                    return ValidationResult(
                        endpoint=endpoint.rule,
                        method=method,
                        status='warning',
                        message=f"Response format issues: {'; '.join(issues)}",
                        response_code=response.status_code
                    )
                    
            except ValueError:
                # Not JSON - check if this is expected
                if 'media' not in endpoint.rule and 'static' not in endpoint.rule:
                    return ValidationResult(
                        endpoint=endpoint.rule,
                        method=method,
                        status='warning',
                        message="Non-JSON response from API endpoint",
                        response_code=response.status_code
                    )
                    
        except Exception as e:
            # Don't report connection errors here as they're handled elsewhere
            if "Connection" not in str(e):
                return ValidationResult(
                    endpoint=endpoint.rule,
                    method=method,
                    status='error',
                    message=f"Validation failed: {str(e)}",
                    error_details=str(e)
                )
        
        return None


def run_api_validation(app: Flask, base_url: str = "http://localhost:5000") -> Dict[str, Any]:
    """Run complete API validation and return results."""
    logger.info("Starting comprehensive API validation...")
    
    # Discovery phase
    discovery = APIEndpointDiscovery(app)
    endpoints = discovery.discover_endpoints()
    
    # Validation phase
    validator = APIEndpointValidator(base_url)
    
    # Run validations
    route_conflicts = discovery.validate_route_conflicts()
    accessibility_results = validator.validate_endpoint_accessibility(endpoints)
    format_results = validator.validate_response_formats(endpoints)
    
    # Generate summary
    endpoint_summary = discovery.generate_endpoint_summary()
    
    # Compile results
    results = {
        'summary': endpoint_summary,
        'endpoints': [asdict(ep) for ep in endpoints],
        'validations': {
            'route_conflicts': [asdict(r) for r in route_conflicts],
            'accessibility': [asdict(r) for r in accessibility_results],
            'response_formats': [asdict(r) for r in format_results]
        },
        'statistics': {
            'total_validations': len(route_conflicts) + len(accessibility_results) + len(format_results),
            'errors': len([r for r in accessibility_results + format_results if r.status == 'error']),
            'warnings': len([r for r in route_conflicts + accessibility_results + format_results if r.status == 'warning']),
            'successes': len([r for r in accessibility_results + format_results if r.status == 'success'])
        }
    }
    
    logger.info(f"API validation completed. Found {results['statistics']['errors']} errors, {results['statistics']['warnings']} warnings")
    
    return results


if __name__ == "__main__":
    # Example usage
    from knowledge_base_agent.web import app
    
    with app.app_context():
        results = run_api_validation(app)
        print(json.dumps(results, indent=2, default=str))