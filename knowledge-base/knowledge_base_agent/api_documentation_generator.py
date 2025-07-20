"""
API Documentation Generator

Generates comprehensive documentation for all API endpoints including
detailed functionality descriptions, usage examples, and integration patterns.
"""

import inspect
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from flask import Flask
import re
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParameterInfo:
    """Information about an endpoint parameter."""
    name: str
    type: str
    required: bool
    description: Optional[str] = None
    example: Optional[Any] = None
    validation: Optional[str] = None


@dataclass
class ResponseInfo:
    """Information about endpoint responses."""
    status_code: int
    description: str
    schema: Optional[Dict] = None
    example: Optional[Dict] = None


@dataclass
class EndpointDocumentation:
    """Comprehensive documentation for an API endpoint."""
    # Basic info
    path: str
    methods: List[str]
    function_name: str
    module: str
    category: str
    
    # Documentation
    summary: str
    description: str
    
    # Parameters
    path_parameters: List[ParameterInfo]
    query_parameters: List[ParameterInfo]
    request_body: Optional[Dict]
    
    # Responses
    responses: List[ResponseInfo]
    
    # Additional info
    authentication_required: bool
    rate_limited: bool
    deprecated: bool
    version: str
    tags: List[str]
    
    # Usage examples
    curl_examples: List[str]
    javascript_examples: List[str]
    python_examples: List[str]
    
    # Integration info
    related_endpoints: List[str]
    workflow_context: Optional[str]
    error_scenarios: List[str]


class APIDocumentationGenerator:
    """Generates comprehensive API documentation."""
    
    def __init__(self, app: Flask, validation_results: Optional[Dict] = None):
        self.app = app
        self.validation_results = validation_results or {}
        self.endpoints_docs: List[EndpointDocumentation] = []
        
    def generate_documentation(self) -> Dict[str, Any]:
        """Generate comprehensive documentation for all endpoints."""
        logger.info("Generating comprehensive API documentation...")
        
        # Discover endpoints
        from .api_validator import APIEndpointDiscovery
        discovery = APIEndpointDiscovery(self.app)
        endpoints = discovery.discover_endpoints()
        
        # Generate documentation for each endpoint
        for endpoint in endpoints:
            if not endpoint.is_deprecated:  # Skip deprecated endpoints for main docs
                doc = self._generate_endpoint_documentation(endpoint)
                self.endpoints_docs.append(doc)
        
        # Organize documentation
        documentation = self._organize_documentation()
        
        logger.info(f"Generated documentation for {len(self.endpoints_docs)} endpoints")
        return documentation
    
    def _generate_endpoint_documentation(self, endpoint) -> EndpointDocumentation:
        """Generate comprehensive documentation for a single endpoint."""
        # Get function for detailed analysis
        view_func = self.app.view_functions.get(endpoint.endpoint)
        
        # Extract basic information
        summary, description = self._extract_summary_and_description(view_func)
        
        # Analyze parameters
        path_params = self._extract_path_parameters(endpoint.rule)
        query_params = self._extract_query_parameters(view_func, endpoint)
        request_body = self._extract_request_body_schema(view_func, endpoint)
        
        # Analyze responses
        responses = self._extract_response_schemas(view_func, endpoint)
        
        # Determine authentication and rate limiting
        auth_required = self._requires_authentication(endpoint)
        rate_limited = self._is_rate_limited(endpoint)
        
        # Extract version and tags
        version = self._extract_version(endpoint.rule)
        tags = self._extract_tags(endpoint)
        
        # Generate examples
        curl_examples = self._generate_curl_examples(endpoint, request_body)
        js_examples = self._generate_javascript_examples(endpoint, request_body)
        py_examples = self._generate_python_examples(endpoint, request_body)
        
        # Find related endpoints and workflow context
        related_endpoints = self._find_related_endpoints(endpoint)
        workflow_context = self._extract_workflow_context(endpoint)
        
        # Extract error scenarios
        error_scenarios = self._extract_error_scenarios(endpoint)
        
        return EndpointDocumentation(
            path=endpoint.rule,
            methods=endpoint.methods,
            function_name=endpoint.function_name,
            module=endpoint.module,
            category=endpoint.category or 'Uncategorized',
            summary=summary,
            description=description,
            path_parameters=path_params,
            query_parameters=query_params,
            request_body=request_body,
            responses=responses,
            authentication_required=auth_required,
            rate_limited=rate_limited,
            deprecated=endpoint.is_deprecated,
            version=version,
            tags=tags,
            curl_examples=curl_examples,
            javascript_examples=js_examples,
            python_examples=py_examples,
            related_endpoints=related_endpoints,
            workflow_context=workflow_context,
            error_scenarios=error_scenarios
        )
    
    def _extract_summary_and_description(self, view_func) -> Tuple[str, str]:
        """Extract summary and description from function docstring."""
        if not view_func or not view_func.__doc__:
            return "No description available", ""
        
        docstring = inspect.getdoc(view_func)
        lines = docstring.split('\n')
        
        # First line is summary
        summary = lines[0].strip() if lines else "No description available"
        
        # Rest is description
        description_lines = []
        for line in lines[1:]:
            line = line.strip()
            if line:
                description_lines.append(line)
        
        description = '\n'.join(description_lines) if description_lines else summary
        
        return summary, description
    
    def _extract_path_parameters(self, rule: str) -> List[ParameterInfo]:
        """Extract path parameters from URL rule."""
        import re
        parameters = []
        
        # Find all path parameters
        param_pattern = r'<(?:(\w+):)?(\w+)>'
        matches = re.findall(param_pattern, rule)
        
        for type_hint, name in matches:
            param_type = type_hint or 'string'
            
            # Map Flask types to standard types
            type_mapping = {
                'int': 'integer',
                'float': 'number',
                'string': 'string',
                'path': 'string'
            }
            
            parameters.append(ParameterInfo(
                name=name,
                type=type_mapping.get(param_type, 'string'),
                required=True,
                description=self._get_parameter_description(name),
                example=self._get_parameter_example(name, param_type)
            ))
        
        return parameters
    
    def _extract_query_parameters(self, view_func, endpoint) -> List[ParameterInfo]:
        """Extract query parameters from function signature and documentation."""
        parameters = []
        
        if not view_func:
            return parameters
        
        # Analyze function signature
        sig = inspect.signature(view_func)
        
        # Look for common query parameter patterns
        common_query_params = {
            'limit': ParameterInfo('limit', 'integer', False, 'Maximum number of results', 10),
            'offset': ParameterInfo('offset', 'integer', False, 'Number of results to skip', 0),
            'page': ParameterInfo('page', 'integer', False, 'Page number', 1),
            'sort': ParameterInfo('sort', 'string', False, 'Sort field', 'created_at'),
            'order': ParameterInfo('order', 'string', False, 'Sort order (asc/desc)', 'desc'),
            'filter': ParameterInfo('filter', 'string', False, 'Filter criteria', ''),
            'search': ParameterInfo('search', 'string', False, 'Search query', ''),
        }
        
        # Add common parameters for list endpoints
        if any(keyword in endpoint.rule.lower() for keyword in ['list', 'all', 'sessions', 'schedules']):
            if 'GET' in endpoint.methods:
                parameters.extend([common_query_params['limit'], common_query_params['offset']])
        
        return parameters
    
    def _extract_request_body_schema(self, view_func, endpoint) -> Optional[Dict]:
        """Extract request body schema for POST/PUT endpoints."""
        if not any(method in endpoint.methods for method in ['POST', 'PUT', 'PATCH']):
            return None
        
        # Define schemas for known endpoints
        schemas = {
            'agent/start': {
                'type': 'object',
                'properties': {
                    'preferences': {
                        'type': 'object',
                        'properties': {
                            'run_mode': {'type': 'string', 'enum': ['full', 'test', 'minimal']},
                            'skip_fetch_bookmarks': {'type': 'boolean'},
                            'skip_process_content': {'type': 'boolean'},
                            'force_recache_tweets': {'type': 'boolean'}
                        }
                    }
                },
                'required': ['preferences']
            },
            'chat': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'model': {'type': 'string'},
                    'session_id': {'type': 'string'}
                },
                'required': ['message']
            },
            'preferences': {
                'type': 'object',
                'properties': {
                    'run_mode': {'type': 'string'},
                    'skip_fetch_bookmarks': {'type': 'boolean'},
                    'skip_process_content': {'type': 'boolean'}
                }
            },
            'schedules': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'frequency': {'type': 'string', 'enum': ['manual', 'daily', 'weekly', 'monthly']},
                    'enabled': {'type': 'boolean'}
                },
                'required': ['name', 'frequency']
            }
        }
        
        # Find matching schema
        for pattern, schema in schemas.items():
            if pattern in endpoint.rule.lower():
                return schema
        
        # Default empty object schema
        return {'type': 'object'}
    
    def _extract_response_schemas(self, view_func, endpoint) -> List[ResponseInfo]:
        """Extract response schemas and status codes."""
        responses = []
        
        # Common success responses
        if 'GET' in endpoint.methods:
            if any(keyword in endpoint.rule for keyword in ['<', 'sessions/', 'schedules/']):
                # Single item endpoint
                responses.append(ResponseInfo(
                    status_code=200,
                    description="Success - returns requested item",
                    example={"id": 1, "data": "..."}
                ))
                responses.append(ResponseInfo(
                    status_code=404,
                    description="Item not found",
                    example={"error": "Item not found"}
                ))
            else:
                # List endpoint
                responses.append(ResponseInfo(
                    status_code=200,
                    description="Success - returns list of items",
                    example={"items": [], "total": 0}
                ))
        
        if 'POST' in endpoint.methods:
            if 'start' in endpoint.rule or 'create' in endpoint.rule:
                responses.append(ResponseInfo(
                    status_code=201,
                    description="Created successfully",
                    example={"success": True, "id": 1}
                ))
            else:
                responses.append(ResponseInfo(
                    status_code=200,
                    description="Operation completed successfully",
                    example={"success": True, "message": "Operation completed"}
                ))
        
        if any(method in endpoint.methods for method in ['PUT', 'PATCH']):
            responses.append(ResponseInfo(
                status_code=200,
                description="Updated successfully",
                example={"success": True, "message": "Updated"}
            ))
        
        if 'DELETE' in endpoint.methods:
            responses.append(ResponseInfo(
                status_code=200,
                description="Deleted successfully",
                example={"success": True, "message": "Deleted"}
            ))
        
        # Common error responses
        responses.extend([
            ResponseInfo(
                status_code=400,
                description="Bad request - invalid parameters",
                example={"error": "Invalid request data"}
            ),
            ResponseInfo(
                status_code=500,
                description="Internal server error",
                example={"error": "Internal server error"}
            )
        ])
        
        return responses
    
    def _requires_authentication(self, endpoint) -> bool:
        """Determine if endpoint requires authentication."""
        # Currently no authentication implemented
        return False
    
    def _is_rate_limited(self, endpoint) -> bool:
        """Determine if endpoint is rate limited."""
        # Currently no rate limiting implemented
        return False
    
    def _extract_version(self, rule: str) -> str:
        """Extract API version from rule."""
        if '/v2/' in rule:
            return 'v2'
        elif '/api/' in rule:
            return 'v1'
        else:
            return 'web'
    
    def _extract_tags(self, endpoint) -> List[str]:
        """Extract tags for endpoint categorization."""
        tags = []
        
        if endpoint.category:
            tags.append(endpoint.category)
        
        if endpoint.is_deprecated:
            tags.append('deprecated')
        
        if 'v2' in endpoint.rule:
            tags.append('v2')
        
        return tags
    
    def _generate_curl_examples(self, endpoint, request_body: Optional[Dict]) -> List[str]:
        """Generate curl command examples."""
        examples = []
        
        for method in endpoint.methods:
            if method in ['HEAD', 'OPTIONS']:
                continue
                
            # Build base URL
            test_url = self._build_example_url(endpoint.rule)
            
            # Build curl command
            curl_parts = [f"curl -X {method}"]
            curl_parts.append(f'"http://localhost:5000{test_url}"')
            
            if method in ['POST', 'PUT', 'PATCH'] and request_body:
                curl_parts.append('-H "Content-Type: application/json"')
                example_data = self._generate_example_request_data(endpoint, request_body)
                curl_parts.append(f"-d '{json.dumps(example_data)}'")
            
            examples.append(' \\\n  '.join(curl_parts))
        
        return examples
    
    def _generate_javascript_examples(self, endpoint, request_body: Optional[Dict]) -> List[str]:
        """Generate JavaScript fetch examples."""
        examples = []
        
        for method in endpoint.methods:
            if method in ['HEAD', 'OPTIONS']:
                continue
                
            test_url = self._build_example_url(endpoint.rule)
            
            js_code = f"""// {method} {endpoint.rule}
const response = await fetch('http://localhost:5000{test_url}', {{
  method: '{method}'"""
            
            if method in ['POST', 'PUT', 'PATCH'] and request_body:
                example_data = self._generate_example_request_data(endpoint, request_body)
                js_code += f""",
  headers: {{
    'Content-Type': 'application/json'
  }},
  body: JSON.stringify({json.dumps(example_data, indent=2)})"""
            
            js_code += """
});

const data = await response.json();
console.log(data);"""
            
            examples.append(js_code)
        
        return examples
    
    def _generate_python_examples(self, endpoint, request_body: Optional[Dict]) -> List[str]:
        """Generate Python requests examples."""
        examples = []
        
        for method in endpoint.methods:
            if method in ['HEAD', 'OPTIONS']:
                continue
                
            test_url = self._build_example_url(endpoint.rule)
            
            py_code = f"""# {method} {endpoint.rule}
import requests

url = 'http://localhost:5000{test_url}'"""
            
            if method in ['POST', 'PUT', 'PATCH'] and request_body:
                example_data = self._generate_example_request_data(endpoint, request_body)
                py_code += f"""
data = {json.dumps(example_data, indent=2)}
response = requests.{method.lower()}(url, json=data)"""
            else:
                py_code += f"""
response = requests.{method.lower()}(url)"""
            
            py_code += """

if response.status_code == 200:
    result = response.json()
    print(result)
else:
    print(f"Error: {response.status_code} - {response.text}")"""
            
            examples.append(py_code)
        
        return examples
    
    def _find_related_endpoints(self, endpoint) -> List[str]:
        """Find related endpoints based on patterns."""
        related = []
        
        # Find endpoints in same category
        category_endpoints = [ep.rule for ep in self.app.url_map.iter_rules() 
                            if self._categorize_endpoint(ep.rule) == endpoint.category]
        
        # Remove current endpoint
        related = [ep for ep in category_endpoints if ep != endpoint.rule]
        
        return related[:5]  # Limit to 5 related endpoints
    
    def _extract_workflow_context(self, endpoint) -> Optional[str]:
        """Extract workflow context for endpoint."""
        workflows = {
            'agent/start': "Part of the agent execution workflow. Use this to start the Knowledge Base Agent with specific preferences.",
            'agent/status': "Monitor agent execution progress. Poll this endpoint to track task completion.",
            'agent/stop': "Stop running agent tasks. Use when you need to cancel ongoing operations.",
            'chat': "Interactive chat with the knowledge base. Send messages to get AI-powered responses.",
            'preferences': "Configure agent behavior. Set processing preferences before starting agent tasks.",
            'schedules': "Manage automated agent execution. Create and manage recurring agent runs."
        }
        
        for pattern, context in workflows.items():
            if pattern in endpoint.rule.lower():
                return context
        
        return None
    
    def _extract_error_scenarios(self, endpoint) -> List[str]:
        """Extract common error scenarios for endpoint."""
        scenarios = []
        
        # Common scenarios based on endpoint type
        if 'start' in endpoint.rule:
            scenarios.extend([
                "Agent already running - returns 400",
                "Invalid preferences format - returns 400",
                "System resources unavailable - returns 503"
            ])
        
        if '<' in endpoint.rule:  # Path parameters
            scenarios.append("Invalid ID format - returns 404")
        
        if any(method in endpoint.methods for method in ['POST', 'PUT', 'PATCH']):
            scenarios.extend([
                "Missing required fields - returns 400",
                "Invalid JSON format - returns 400"
            ])
        
        # Add validation results if available
        if self.validation_results:
            validation_errors = self.validation_results.get('validations', {}).get('accessibility', [])
            for error in validation_errors:
                if error.get('endpoint') == endpoint.rule and error.get('status') == 'error':
                    scenarios.append(f"Validation error: {error.get('message')}")
        
        return scenarios
    
    def _build_example_url(self, rule: str) -> str:
        """Build example URL with realistic parameter values."""
        import re
        url = rule
        
        # Replace path parameters with examples
        replacements = {
            r'<int:(\w+)>': lambda m: '1' if 'id' in m.group(1) else '123',
            r'<string:(\w+)>': lambda m: 'example' if 'name' in m.group(1) else 'test',
            r'<(\w+)>': 'example',
            r'<path:(\w+)>': 'path/to/file'
        }
        
        for pattern, replacement in replacements.items():
            if callable(replacement):
                url = re.sub(pattern, replacement, url)
            else:
                url = re.sub(pattern, replacement, url)
        
        return url
    
    def _generate_example_request_data(self, endpoint, schema: Dict) -> Dict:
        """Generate example request data based on schema."""
        if not schema or schema.get('type') != 'object':
            return {}
        
        example_data = {}
        properties = schema.get('properties', {})
        
        for field, field_schema in properties.items():
            field_type = field_schema.get('type', 'string')
            
            if field_type == 'string':
                if 'enum' in field_schema:
                    example_data[field] = field_schema['enum'][0]
                else:
                    example_data[field] = f"example_{field}"
            elif field_type == 'boolean':
                example_data[field] = True
            elif field_type == 'integer':
                example_data[field] = 1
            elif field_type == 'object':
                example_data[field] = self._generate_example_request_data(endpoint, field_schema)
        
        return example_data
    
    def _categorize_endpoint(self, rule: str) -> str:
        """Categorize endpoint - same logic as in api_validator."""
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
    
    def _get_parameter_description(self, name: str) -> str:
        """Get description for common parameter names."""
        descriptions = {
            'id': 'Unique identifier',
            'task_id': 'Task identifier for tracking',
            'session_id': 'Chat session identifier',
            'schedule_id': 'Schedule identifier',
            'filename': 'Name of the file',
            'variable_name': 'Environment variable name',
            'synthesis_id': 'Synthesis document identifier',
            'item_id': 'Knowledge base item identifier',
            'run_id': 'Schedule run identifier',
            'page_name': 'Page name for UI routing'
        }
        return descriptions.get(name, f'{name.replace("_", " ").title()} parameter')
    
    def _get_parameter_example(self, name: str, param_type: str) -> Any:
        """Get example value for parameter."""
        if param_type == 'int':
            return 1 if 'id' in name else 123
        elif param_type == 'string':
            if 'id' in name:
                return 'abc123'
            elif 'name' in name:
                return 'example_name'
            else:
                return 'example'
        elif param_type == 'path':
            return 'path/to/resource'
        else:
            return 'example'
    
    def _organize_documentation(self) -> Dict[str, Any]:
        """Organize documentation into structured format."""
        # Group by category
        by_category = {}
        for doc in self.endpoints_docs:
            category = doc.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(asdict(doc))
        
        # Generate statistics
        stats = {
            'total_endpoints': len(self.endpoints_docs),
            'by_category': {cat: len(docs) for cat, docs in by_category.items()},
            'by_version': {
                'v1': len([d for d in self.endpoints_docs if d.version == 'v1']),
                'v2': len([d for d in self.endpoints_docs if d.version == 'v2']),
                'web': len([d for d in self.endpoints_docs if d.version == 'web'])
            },
            'by_method': {}
        }
        
        # Count by HTTP method
        all_methods = []
        for doc in self.endpoints_docs:
            all_methods.extend(doc.methods)
        
        for method in set(all_methods):
            stats['by_method'][method] = all_methods.count(method)
        
        return {
            'metadata': {
                'generated_at': '2024-01-01T00:00:00Z',  # Would use actual timestamp
                'version': '1.0.0',
                'base_url': 'http://localhost:5000'
            },
            'statistics': stats,
            'categories': by_category,
            'endpoints': [asdict(doc) for doc in self.endpoints_docs]
        }


def generate_api_documentation(app: Flask, validation_results: Optional[Dict] = None) -> Dict[str, Any]:
    """Generate comprehensive API documentation."""
    generator = APIDocumentationGenerator(app, validation_results)
    return generator.generate_documentation()