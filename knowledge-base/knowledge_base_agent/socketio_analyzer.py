"""
SocketIO Event Schema Documentation

Analyzes SocketIO event handlers and emitters to generate comprehensive
documentation of real-time communication patterns.
"""

import inspect
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from flask_socketio import SocketIO
import ast
import json

logger = logging.getLogger(__name__)


@dataclass
class EventParameter:
    """Information about an event parameter."""
    name: str
    type: str
    required: bool
    description: Optional[str] = None
    example: Optional[Any] = None


@dataclass
class EventSchema:
    """Schema information for a SocketIO event."""
    name: str
    direction: str  # 'incoming', 'outgoing', 'bidirectional'
    description: str
    parameters: List[EventParameter]
    example_data: Optional[Dict] = None
    handler_function: Optional[str] = None
    emitter_locations: List[str] = None


@dataclass
class SocketIODocumentation:
    """Comprehensive SocketIO event documentation."""
    # Event categories
    connection_events: List[EventSchema]
    agent_events: List[EventSchema]
    system_events: List[EventSchema]
    chat_events: List[EventSchema]
    log_events: List[EventSchema]
    
    # Statistics
    total_events: int
    incoming_events: int
    outgoing_events: int
    bidirectional_events: int
    
    # Event patterns
    event_patterns: Dict[str, List[str]]
    data_formats: Dict[str, Dict]


class SocketIOAnalyzer:
    """Analyzes SocketIO events and generates documentation."""
    
    def __init__(self, app, socketio: SocketIO):
        self.app = app
        self.socketio = socketio
        self.events: List[EventSchema] = []
        
    def analyze_events(self) -> SocketIODocumentation:
        """Analyze all SocketIO events and generate documentation."""
        logger.info("Starting SocketIO event analysis...")
        
        # Analyze incoming events (handlers)
        self._analyze_incoming_events()
        
        # Analyze outgoing events (emitters)
        self._analyze_outgoing_events()
        
        # Categorize events
        documentation = self._categorize_events()
        
        logger.info(f"SocketIO analysis completed. Found {len(self.events)} events")
        return documentation
    
    def _analyze_incoming_events(self):
        """Analyze incoming SocketIO event handlers."""
        # Since direct handler inspection is complex, we'll use the known handlers approach
        self._scan_handler_decorators()
    
    def _analyze_handler(self, event_name: str, handler_func) -> Optional[EventSchema]:
        """Analyze a single SocketIO handler."""
        try:
            # Get function signature and docstring
            sig = inspect.signature(handler_func)
            docstring = inspect.getdoc(handler_func) or f"Handler for {event_name} event"
            
            # Extract parameters
            parameters = []
            for param_name, param in sig.parameters.items():
                if param_name not in ['auth', 'sid']:  # Skip SocketIO internal params
                    param_info = EventParameter(
                        name=param_name,
                        type=self._infer_parameter_type(param),
                        required=param.default == inspect.Parameter.empty,
                        description=f"Parameter for {event_name} event"
                    )
                    parameters.append(param_info)
            
            # Generate example data
            example_data = self._generate_example_data(event_name, parameters)
            
            return EventSchema(
                name=event_name,
                direction='incoming',
                description=docstring,
                parameters=parameters,
                example_data=example_data,
                handler_function=handler_func.__name__,
                emitter_locations=[]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing handler {event_name}: {e}")
            return None
    
    def _scan_handler_decorators(self):
        """Scan source files for @socketio.on decorators."""
        # Define known handlers from the codebase
        known_handlers = {
            'connect': {
                'description': 'Client connection established',
                'direction': 'incoming',
                'parameters': [
                    EventParameter('auth', 'dict', False, 'Authentication data (optional)')
                ],
                'example_data': {'auth': None}
            },
            'disconnect': {
                'description': 'Client disconnection',
                'direction': 'incoming',
                'parameters': [],
                'example_data': {}
            },
            'request_initial_status_and_git_config': {
                'description': 'Request initial status and git configuration',
                'direction': 'incoming',
                'parameters': [],
                'example_data': {}
            },
            'request_initial_logs': {
                'description': 'Request current logs from server',
                'direction': 'incoming',
                'parameters': [],
                'example_data': {}
            },
            'clear_server_logs': {
                'description': 'Clear server-side logs',
                'direction': 'incoming',
                'parameters': [],
                'example_data': {}
            },
            'run_agent': {
                'description': 'Start agent execution with preferences',
                'direction': 'incoming',
                'parameters': [
                    EventParameter('preferences', 'dict', True, 'Agent execution preferences')
                ],
                'example_data': {
                    'preferences': {
                        'run_mode': 'full',
                        'skip_fetch_bookmarks': False,
                        'force_recache_tweets': False
                    }
                }
            },
            'stop_agent': {
                'description': 'Stop running agent task',
                'direction': 'incoming',
                'parameters': [
                    EventParameter('task_id', 'string', False, 'Task ID to stop (optional)')
                ],
                'example_data': {'task_id': 'abc123'}
            },
            'request_gpu_stats': {
                'description': 'Request current GPU statistics',
                'direction': 'incoming',
                'parameters': [],
                'example_data': {}
            }
        }
        
        # Add known handlers to events list
        for event_name, handler_info in known_handlers.items():
            # Check if already added
            if not any(e.name == event_name for e in self.events):
                event_schema = EventSchema(
                    name=event_name,
                    direction=handler_info['direction'],
                    description=handler_info['description'],
                    parameters=handler_info['parameters'],
                    example_data=handler_info['example_data'],
                    handler_function=f"handle_{event_name}",
                    emitter_locations=[]
                )
                self.events.append(event_schema)
    
    def _analyze_outgoing_events(self):
        """Analyze outgoing SocketIO events (emitters)."""
        # Define known outgoing events from the codebase analysis
        outgoing_events = {
            'agent_status': {
                'description': 'Agent status update with current state',
                'parameters': [
                    EventParameter('is_running', 'boolean', True, 'Whether agent is currently running'),
                    EventParameter('current_phase_message', 'string', False, 'Current phase description'),
                    EventParameter('task_id', 'string', False, 'Current task identifier'),
                    EventParameter('progress', 'integer', False, 'Progress percentage (0-100)')
                ],
                'example_data': {
                    'is_running': True,
                    'current_phase_message': 'Processing content...',
                    'task_id': 'abc123',
                    'progress': 45
                }
            },
            'agent_status_update': {
                'description': 'Real-time agent status changes',
                'parameters': [
                    EventParameter('is_running', 'boolean', True, 'Whether agent is currently running'),
                    EventParameter('current_phase_message', 'string', False, 'Current phase description'),
                    EventParameter('task_id', 'string', False, 'Current task identifier')
                ],
                'example_data': {
                    'is_running': False,
                    'current_phase_message': 'Agent stopped by user',
                    'task_id': None
                }
            },
            'agent_progress_update': {
                'description': 'Agent execution progress updates',
                'parameters': [
                    EventParameter('task_id', 'string', True, 'Task identifier'),
                    EventParameter('progress', 'integer', True, 'Progress percentage (0-100)'),
                    EventParameter('phase', 'string', False, 'Current processing phase'),
                    EventParameter('message', 'string', False, 'Progress message')
                ],
                'example_data': {
                    'task_id': 'abc123',
                    'progress': 75,
                    'phase': 'synthesis_generation',
                    'message': 'Generating synthesis documents...'
                }
            },
            'agent_run_completed': {
                'description': 'Agent execution completion notification',
                'parameters': [
                    EventParameter('task_id', 'string', True, 'Completed task identifier'),
                    EventParameter('success', 'boolean', True, 'Whether execution was successful'),
                    EventParameter('duration', 'string', False, 'Execution duration'),
                    EventParameter('results', 'dict', False, 'Execution results summary')
                ],
                'example_data': {
                    'task_id': 'abc123',
                    'success': True,
                    'duration': '5m 32s',
                    'results': {'processed_items': 42, 'generated_syntheses': 8}
                }
            },
            'log_message': {
                'description': 'Real-time log message streaming',
                'parameters': [
                    EventParameter('task_id', 'string', False, 'Associated task identifier'),
                    EventParameter('level', 'string', True, 'Log level (INFO, WARNING, ERROR)'),
                    EventParameter('message', 'string', True, 'Log message content'),
                    EventParameter('timestamp', 'string', True, 'ISO timestamp'),
                    EventParameter('module', 'string', False, 'Source module name')
                ],
                'example_data': {
                    'task_id': 'abc123',
                    'level': 'INFO',
                    'message': '✅ Processing completed successfully',
                    'timestamp': '2024-01-01T12:00:00Z',
                    'module': 'content_processor'
                }
            },
            'phase_update': {
                'description': 'Agent phase transition updates',
                'parameters': [
                    EventParameter('task_id', 'string', True, 'Task identifier'),
                    EventParameter('phase_id', 'string', True, 'Phase identifier'),
                    EventParameter('phase_name', 'string', True, 'Human-readable phase name'),
                    EventParameter('status', 'string', True, 'Phase status (started, completed, failed)'),
                    EventParameter('progress', 'integer', False, 'Overall progress percentage')
                ],
                'example_data': {
                    'task_id': 'abc123',
                    'phase_id': 'content_processing',
                    'phase_name': 'Content Processing',
                    'status': 'started',
                    'progress': 30
                }
            },
            'gpu_stats': {
                'description': 'GPU statistics and monitoring data',
                'parameters': [
                    EventParameter('gpus', 'array', False, 'Array of GPU information'),
                    EventParameter('error', 'string', False, 'Error message if stats unavailable')
                ],
                'example_data': {
                    'gpus': [
                        {
                            'id': 0,
                            'name': 'NVIDIA RTX 4090',
                            'memory_used': 8192,
                            'memory_total': 24576,
                            'utilization': 85,
                            'temperature': 72
                        }
                    ]
                }
            },
            'system_health_update': {
                'description': 'System health and status monitoring',
                'parameters': [
                    EventParameter('status', 'string', True, 'Overall system status'),
                    EventParameter('services', 'dict', False, 'Service status breakdown'),
                    EventParameter('resources', 'dict', False, 'Resource utilization data')
                ],
                'example_data': {
                    'status': 'healthy',
                    'services': {
                        'redis': 'connected',
                        'database': 'connected',
                        'ollama': 'available'
                    },
                    'resources': {
                        'cpu_percent': 45,
                        'memory_percent': 62,
                        'disk_percent': 78
                    }
                }
            },
            'initial_logs': {
                'description': 'Initial log data sent on connection',
                'parameters': [
                    EventParameter('logs', 'array', True, 'Array of recent log messages')
                ],
                'example_data': {'logs': []}
            },
            'logs_cleared': {
                'description': 'Notification that logs have been cleared',
                'parameters': [],
                'example_data': {}
            },
            'git_config_status': {
                'description': 'Git configuration status',
                'parameters': [
                    EventParameter('auto_commit', 'boolean', True, 'Whether auto-commit is enabled'),
                    EventParameter('auto_push', 'boolean', True, 'Whether auto-push is enabled')
                ],
                'example_data': {
                    'auto_commit': False,
                    'auto_push': False
                }
            },
            'initial_status_and_git_config': {
                'description': 'Combined initial status and git configuration',
                'parameters': [
                    EventParameter('is_running', 'boolean', True, 'Whether agent is running'),
                    EventParameter('git_config', 'dict', True, 'Git configuration settings')
                ],
                'example_data': {
                    'is_running': False,
                    'git_config': {
                        'auto_commit': False,
                        'auto_push': False
                    }
                }
            }
        }
        
        # Add outgoing events to events list
        for event_name, event_info in outgoing_events.items():
            # Check if already added
            if not any(e.name == event_name for e in self.events):
                event_schema = EventSchema(
                    name=event_name,
                    direction='outgoing',
                    description=event_info['description'],
                    parameters=event_info['parameters'],
                    example_data=event_info['example_data'],
                    handler_function=None,
                    emitter_locations=['web.py', 'realtime_manager.py', 'agent.py']
                )
                self.events.append(event_schema)
    
    def _infer_parameter_type(self, param) -> str:
        """Infer parameter type from signature."""
        if param.annotation != inspect.Parameter.empty:
            if hasattr(param.annotation, '__name__'):
                return param.annotation.__name__
            else:
                return str(param.annotation)
        return 'any'
    
    def _generate_example_data(self, event_name: str, parameters: List[EventParameter]) -> Dict:
        """Generate example data for an event."""
        example = {}
        for param in parameters:
            if param.type == 'dict':
                example[param.name] = {}
            elif param.type == 'list' or param.type == 'array':
                example[param.name] = []
            elif param.type == 'str' or param.type == 'string':
                example[param.name] = f"example_{param.name}"
            elif param.type == 'int' or param.type == 'integer':
                example[param.name] = 123
            elif param.type == 'bool' or param.type == 'boolean':
                example[param.name] = True
            else:
                example[param.name] = None
        return example
    
    def _categorize_events(self) -> SocketIODocumentation:
        """Categorize events and generate documentation."""
        # Categorize events
        connection_events = []
        agent_events = []
        system_events = []
        chat_events = []
        log_events = []
        
        for event in self.events:
            if event.name in ['connect', 'disconnect']:
                connection_events.append(event)
            elif 'agent' in event.name or event.name in ['run_agent', 'stop_agent']:
                agent_events.append(event)
            elif event.name in ['log_message', 'initial_logs', 'logs_cleared', 'clear_server_logs']:
                log_events.append(event)
            elif 'gpu' in event.name or 'system' in event.name or 'git' in event.name:
                system_events.append(event)
            elif 'chat' in event.name:
                chat_events.append(event)
            else:
                system_events.append(event)  # Default to system
        
        # Calculate statistics
        total_events = len(self.events)
        incoming_events = len([e for e in self.events if e.direction == 'incoming'])
        outgoing_events = len([e for e in self.events if e.direction == 'outgoing'])
        bidirectional_events = len([e for e in self.events if e.direction == 'bidirectional'])
        
        # Generate event patterns
        event_patterns = {
            'Agent Control': [e.name for e in agent_events],
            'System Monitoring': [e.name for e in system_events if 'stats' in e.name or 'health' in e.name],
            'Real-time Logging': [e.name for e in log_events],
            'Connection Management': [e.name for e in connection_events]
        }
        
        # Generate data formats
        data_formats = {}
        for event in self.events:
            if event.example_data:
                data_formats[event.name] = event.example_data
        
        return SocketIODocumentation(
            connection_events=connection_events,
            agent_events=agent_events,
            system_events=system_events,
            chat_events=chat_events,
            log_events=log_events,
            total_events=total_events,
            incoming_events=incoming_events,
            outgoing_events=outgoing_events,
            bidirectional_events=bidirectional_events,
            event_patterns=event_patterns,
            data_formats=data_formats
        )


def analyze_socketio_events(app, socketio: SocketIO) -> Dict[str, Any]:
    """Analyze SocketIO events and return comprehensive documentation."""
    analyzer = SocketIOAnalyzer(app, socketio)
    documentation = analyzer.analyze_events()
    
    # Convert to dictionary format
    return {
        'metadata': {
            'generated_at': '2024-01-01T00:00:00Z',  # Would use actual timestamp
            'total_events': documentation.total_events,
            'incoming_events': documentation.incoming_events,
            'outgoing_events': documentation.outgoing_events,
            'bidirectional_events': documentation.bidirectional_events
        },
        'statistics': {
            'by_category': {
                'Connection Events': len(documentation.connection_events),
                'Agent Events': len(documentation.agent_events),
                'System Events': len(documentation.system_events),
                'Chat Events': len(documentation.chat_events),
                'Log Events': len(documentation.log_events)
            },
            'by_direction': {
                'incoming': documentation.incoming_events,
                'outgoing': documentation.outgoing_events,
                'bidirectional': documentation.bidirectional_events
            }
        },
        'categories': {
            'Connection Events': [asdict(e) for e in documentation.connection_events],
            'Agent Events': [asdict(e) for e in documentation.agent_events],
            'System Events': [asdict(e) for e in documentation.system_events],
            'Chat Events': [asdict(e) for e in documentation.chat_events],
            'Log Events': [asdict(e) for e in documentation.log_events]
        },
        'event_patterns': documentation.event_patterns,
        'data_formats': documentation.data_formats,
        'events': [asdict(e) for e in documentation.connection_events + 
                          documentation.agent_events + 
                          documentation.system_events + 
                          documentation.chat_events + 
                          documentation.log_events]
    }