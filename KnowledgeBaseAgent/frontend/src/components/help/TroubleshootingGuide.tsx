import React, { useState } from 'react'
import { Search, ChevronDown, ChevronRight, AlertTriangle, CheckCircle, ExternalLink, Copy } from 'lucide-react'
import { GlassCard } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/utils/cn'

interface TroubleshootingItem {
  id: string
  title: string
  category: 'connection' | 'performance' | 'ai-models' | 'pipeline' | 'ui' | 'general'
  severity: 'low' | 'medium' | 'high' | 'critical'
  symptoms: string[]
  causes: string[]
  solutions: {
    title: string
    steps: string[]
    code?: string
    links?: { title: string; url: string }[]
  }[]
  tags: string[]
}

const troubleshootingData: TroubleshootingItem[] = [
  {
    id: 'websocket-connection-failed',
    title: 'WebSocket Connection Failed',
    category: 'connection',
    severity: 'high',
    symptoms: [
      'Real-time updates not working',
      'Pipeline progress not updating',
      'Connection indicator shows disconnected',
      'Error notifications about WebSocket failures'
    ],
    causes: [
      'WebSocket server is down',
      'Network firewall blocking WebSocket connections',
      'Proxy server not configured for WebSocket',
      'Browser blocking WebSocket connections'
    ],
    solutions: [
      {
        title: 'Check WebSocket Server Status',
        steps: [
          'Open browser developer tools (F12)',
          'Go to Network tab',
          'Look for WebSocket connection attempts',
          'Check if connection is being established',
          'Verify WebSocket URL in environment configuration'
        ]
      },
      {
        title: 'Configure Firewall/Proxy',
        steps: [
          'Allow WebSocket connections through firewall',
          'Configure proxy to support WebSocket upgrade',
          'Check corporate network policies',
          'Try connecting from different network'
        ]
      },
      {
        title: 'Manual Reconnection',
        steps: [
          'Click the connection indicator in the top bar',
          'Select "Reconnect" from the dropdown',
          'Wait for connection to be established',
          'Refresh the page if reconnection fails'
        ]
      }
    ],
    tags: ['websocket', 'connection', 'real-time', 'network']
  },
  {
    id: 'ai-model-not-responding',
    title: 'AI Model Not Responding',
    category: 'ai-models',
    severity: 'critical',
    symptoms: [
      'AI model test failures',
      'Pipeline phases hanging on AI processing',
      'Timeout errors in AI operations',
      'Model status showing as unavailable'
    ],
    causes: [
      'AI service (Ollama/LocalAI) is not running',
      'Model not downloaded or corrupted',
      'Insufficient system resources (RAM/GPU)',
      'Network connectivity issues to AI service'
    ],
    solutions: [
      {
        title: 'Check AI Service Status',
        steps: [
          'Verify Ollama/LocalAI service is running',
          'Check service logs for errors',
          'Test direct connection to AI service',
          'Restart AI service if necessary'
        ],
        code: `# Check Ollama status
curl http://localhost:11434/api/tags

# Check LocalAI status  
curl http://localhost:8080/v1/models`
      },
      {
        title: 'Verify Model Availability',
        steps: [
          'Go to AI Models configuration page',
          'Run model connectivity tests',
          'Download missing models if needed',
          'Check model file integrity'
        ]
      },
      {
        title: 'Resource Optimization',
        steps: [
          'Check system RAM usage',
          'Monitor GPU memory if using GPU models',
          'Close unnecessary applications',
          'Consider using smaller models if resources are limited'
        ]
      }
    ],
    tags: ['ai', 'models', 'ollama', 'localai', 'timeout']
  },
  {
    id: 'pipeline-phase-stuck',
    title: 'Pipeline Phase Stuck or Failing',
    category: 'pipeline',
    severity: 'high',
    symptoms: [
      'Pipeline phase shows "running" for extended time',
      'Phase progress not updating',
      'Error messages in phase execution',
      'Pipeline status shows failed'
    ],
    causes: [
      'AI model timeout or failure',
      'Network connectivity issues',
      'Insufficient system resources',
      'Invalid configuration or data'
    ],
    solutions: [
      {
        title: 'Reset Pipeline Phase',
        steps: [
          'Go to Pipeline Dashboard',
          'Find the stuck phase',
          'Click "Reset Phase" button',
          'Wait for phase to reset',
          'Retry phase execution'
        ]
      },
      {
        title: 'Check Phase Dependencies',
        steps: [
          'Verify previous phases completed successfully',
          'Check required data is available',
          'Validate AI model configuration for the phase',
          'Review phase-specific requirements'
        ]
      },
      {
        title: 'Manual Phase Execution',
        steps: [
          'Use diagnostic tools to test phase components',
          'Execute phase with reduced data set',
          'Check logs for specific error messages',
          'Contact support with error details if needed'
        ]
      }
    ],
    tags: ['pipeline', 'phases', 'stuck', 'timeout', 'execution']
  },
  {
    id: 'slow-performance',
    title: 'Slow Dashboard Performance',
    category: 'performance',
    severity: 'medium',
    symptoms: [
      'Dashboard loading slowly',
      'Laggy animations and transitions',
      'High memory usage in browser',
      'Unresponsive user interface'
    ],
    causes: [
      'Too many browser tabs open',
      'Large datasets being processed',
      'Memory leaks in application',
      'Slow network connection'
    ],
    solutions: [
      {
        title: 'Browser Optimization',
        steps: [
          'Close unnecessary browser tabs',
          'Clear browser cache and cookies',
          'Disable browser extensions temporarily',
          'Restart browser to free up memory'
        ]
      },
      {
        title: 'Application Settings',
        steps: [
          'Reduce real-time update frequency',
          'Limit number of items displayed per page',
          'Disable animations if needed',
          'Use simplified view modes'
        ]
      },
      {
        title: 'System Resources',
        steps: [
          'Check system RAM usage',
          'Close other applications',
          'Restart computer if necessary',
          'Consider upgrading hardware'
        ]
      }
    ],
    tags: ['performance', 'slow', 'memory', 'browser', 'optimization']
  },
  {
    id: 'twitter-api-errors',
    title: 'Twitter API Connection Issues',
    category: 'connection',
    severity: 'high',
    symptoms: [
      'Unable to fetch Twitter bookmarks',
      'Twitter API rate limit errors',
      'Authentication failures',
      'Tweet data not loading'
    ],
    causes: [
      'Invalid Twitter API credentials',
      'API rate limits exceeded',
      'Twitter API service issues',
      'Network connectivity problems'
    ],
    solutions: [
      {
        title: 'Verify API Credentials',
        steps: [
          'Check Twitter API bearer token',
          'Verify token has required permissions',
          'Test token with Twitter API directly',
          'Regenerate token if necessary'
        ],
        code: `# Test Twitter API token
curl -H "Authorization: Bearer YOUR_TOKEN" \\
  "https://api.twitter.com/2/users/me"`
      },
      {
        title: 'Handle Rate Limits',
        steps: [
          'Wait for rate limit window to reset',
          'Reduce frequency of API calls',
          'Implement proper rate limiting',
          'Use bookmark export files as alternative'
        ]
      },
      {
        title: 'Alternative Data Sources',
        steps: [
          'Export bookmarks from Twitter/X',
          'Upload bookmark JSON file',
          'Use cached data when available',
          'Process bookmarks in smaller batches'
        ]
      }
    ],
    tags: ['twitter', 'api', 'authentication', 'rate-limit', 'bookmarks']
  },
  {
    id: 'ui-components-not-loading',
    title: 'UI Components Not Loading Properly',
    category: 'ui',
    severity: 'medium',
    symptoms: [
      'Blank or missing components',
      'Styling issues or broken layout',
      'JavaScript errors in console',
      'Components not responding to interactions'
    ],
    causes: [
      'JavaScript errors preventing component rendering',
      'CSS loading issues',
      'Browser compatibility problems',
      'Corrupted browser cache'
    ],
    solutions: [
      {
        title: 'Clear Browser Cache',
        steps: [
          'Open browser settings',
          'Go to Privacy/Security section',
          'Clear browsing data',
          'Select "Cached images and files"',
          'Refresh the page'
        ]
      },
      {
        title: 'Check Browser Console',
        steps: [
          'Open developer tools (F12)',
          'Go to Console tab',
          'Look for JavaScript errors',
          'Note error messages and line numbers',
          'Report errors to support team'
        ]
      },
      {
        title: 'Browser Compatibility',
        steps: [
          'Try using a different browser',
          'Update browser to latest version',
          'Disable browser extensions',
          'Check if browser supports required features'
        ]
      }
    ],
    tags: ['ui', 'components', 'rendering', 'browser', 'cache']
  }
]

interface TroubleshootingGuideProps {
  className?: string
}

export function TroubleshootingGuide({ className }: TroubleshootingGuideProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

  const categories = [
    { id: 'all', name: 'All Issues', count: troubleshootingData.length },
    { id: 'connection', name: 'Connection', count: troubleshootingData.filter(item => item.category === 'connection').length },
    { id: 'ai-models', name: 'AI Models', count: troubleshootingData.filter(item => item.category === 'ai-models').length },
    { id: 'pipeline', name: 'Pipeline', count: troubleshootingData.filter(item => item.category === 'pipeline').length },
    { id: 'performance', name: 'Performance', count: troubleshootingData.filter(item => item.category === 'performance').length },
    { id: 'ui', name: 'UI Issues', count: troubleshootingData.filter(item => item.category === 'ui').length }
  ]

  const filteredItems = troubleshootingData.filter(item => {
    const matchesSearch = searchTerm === '' || 
      item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.symptoms.some(symptom => symptom.toLowerCase().includes(searchTerm.toLowerCase())) ||
      item.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))
    
    const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory
    
    return matchesSearch && matchesCategory
  })

  const toggleExpanded = (itemId: string) => {
    setExpandedItems(prev => {
      const newSet = new Set(prev)
      if (newSet.has(itemId)) {
        newSet.delete(itemId)
      } else {
        newSet.add(itemId)
      }
      return newSet
    })
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-500 bg-red-50'
      case 'high': return 'text-orange-500 bg-orange-50'
      case 'medium': return 'text-yellow-500 bg-yellow-50'
      case 'low': return 'text-green-500 bg-green-50'
      default: return 'text-gray-500 bg-gray-50'
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Troubleshooting Guide</h2>
          <p className="text-muted-foreground">Find solutions to common issues and problems</p>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search issues, symptoms, or solutions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <div className="flex gap-2 flex-wrap">
          {categories.map(category => (
            <Button
              key={category.id}
              variant={selectedCategory === category.id ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(category.id)}
            >
              {category.name}
              <Badge variant="secondary" className="ml-2">
                {category.count}
              </Badge>
            </Button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="space-y-4">
        {filteredItems.length === 0 ? (
          <GlassCard className="p-8 text-center">
            <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No matching issues found</h3>
            <p className="text-muted-foreground">
              Try adjusting your search terms or browse different categories
            </p>
          </GlassCard>
        ) : (
          filteredItems.map(item => (
            <TroubleshootingCard
              key={item.id}
              item={item}
              isExpanded={expandedItems.has(item.id)}
              onToggleExpanded={() => toggleExpanded(item.id)}
              onCopyCode={copyToClipboard}
            />
          ))
        )}
      </div>
    </div>
  )
}

interface TroubleshootingCardProps {
  item: TroubleshootingItem
  isExpanded: boolean
  onToggleExpanded: () => void
  onCopyCode: (code: string) => void
}

function TroubleshootingCard({ item, isExpanded, onToggleExpanded, onCopyCode }: TroubleshootingCardProps) {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'border-red-500 bg-red-50/10'
      case 'high': return 'border-orange-500 bg-orange-50/10'
      case 'medium': return 'border-yellow-500 bg-yellow-50/10'
      case 'low': return 'border-green-500 bg-green-50/10'
      default: return 'border-gray-500 bg-gray-50/10'
    }
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical': return <Badge variant="destructive">Critical</Badge>
      case 'high': return <Badge className="bg-orange-500 text-white">High</Badge>
      case 'medium': return <Badge className="bg-yellow-500 text-white">Medium</Badge>
      case 'low': return <Badge className="bg-green-500 text-white">Low</Badge>
      default: return <Badge variant="outline">Unknown</Badge>
    }
  }

  return (
    <GlassCard className={cn('border-l-4', getSeverityColor(item.severity))}>
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-lg font-medium">{item.title}</h3>
              {getSeverityBadge(item.severity)}
              <Badge variant="outline" className="capitalize">
                {item.category.replace('-', ' ')}
              </Badge>
            </div>
            
            <div className="flex flex-wrap gap-1 mb-3">
              {item.tags.map(tag => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleExpanded}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        </div>

        {isExpanded && (
          <div className="space-y-6">
            {/* Symptoms */}
            <div>
              <h4 className="font-medium mb-2 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-orange-500" />
                Symptoms
              </h4>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                {item.symptoms.map((symptom, index) => (
                  <li key={index}>{symptom}</li>
                ))}
              </ul>
            </div>

            {/* Possible Causes */}
            <div>
              <h4 className="font-medium mb-2">Possible Causes</h4>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                {item.causes.map((cause, index) => (
                  <li key={index}>{cause}</li>
                ))}
              </ul>
            </div>

            {/* Solutions */}
            <div>
              <h4 className="font-medium mb-3 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                Solutions
              </h4>
              
              <div className="space-y-4">
                {item.solutions.map((solution, index) => (
                  <div key={index} className="border rounded-lg p-4 bg-muted/50">
                    <h5 className="font-medium mb-2">{solution.title}</h5>
                    
                    <ol className="list-decimal list-inside space-y-1 text-sm mb-3">
                      {solution.steps.map((step, stepIndex) => (
                        <li key={stepIndex} className="text-muted-foreground">{step}</li>
                      ))}
                    </ol>
                    
                    {solution.code && (
                      <div className="relative">
                        <pre className="bg-black text-green-400 p-3 rounded text-xs overflow-x-auto">
                          <code>{solution.code}</code>
                        </pre>
                        <Button
                          size="sm"
                          variant="outline"
                          className="absolute top-2 right-2"
                          onClick={() => onCopyCode(solution.code!)}
                        >
                          <Copy className="h-3 w-3" />
                        </Button>
                      </div>
                    )}
                    
                    {solution.links && solution.links.length > 0 && (
                      <div className="mt-3">
                        <div className="text-sm font-medium mb-2">Related Links:</div>
                        <div className="space-y-1">
                          {solution.links.map((link, linkIndex) => (
                            <a
                              key={linkIndex}
                              href={link.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                            >
                              <ExternalLink className="h-3 w-3" />
                              {link.title}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </GlassCard>
  )
}