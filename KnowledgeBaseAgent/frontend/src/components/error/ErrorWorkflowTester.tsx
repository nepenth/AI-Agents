import React, { useState } from 'react'
import { AlertTriangle, Play, RotateCcw, BarChart3 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { GlassCard } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { ErrorTestingUtils } from '@/utils/errorTesting'
import { errorService } from '@/services/errorService'

interface ErrorWorkflowTesterProps {
  onClose?: () => void
}

export function ErrorWorkflowTester({ onClose }: ErrorWorkflowTesterProps) {
  const [stats, setStats] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)

  const updateStats = () => {
    setStats(ErrorTestingUtils.getErrorStats())
  }

  const runErrorTest = async (testFn: () => void, testName: string) => {
    setIsRunning(true)
    try {
      console.log(`Running test: ${testName}`)
      testFn()
      setTimeout(updateStats, 500) // Allow time for error to be processed
    } catch (error) {
      console.error(`Test failed: ${testName}`, error)
    } finally {
      setIsRunning(false)
    }
  }

  const runRecoveryTest = async () => {
    setIsRunning(true)
    try {
      const actions = await ErrorTestingUtils.testRecoveryActions()
      console.log('Recovery actions test completed:', actions)
      updateStats()
    } catch (error) {
      console.error('Recovery test failed:', error)
    } finally {
      setIsRunning(false)
    }
  }

  const clearAllErrors = () => {
    ErrorTestingUtils.clearTestErrors()
    setStats(null)
  }

  React.useEffect(() => {
    updateStats()
  }, [])

  if (!import.meta.env?.DEV) {
    return null // Only show in development
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <GlassCard className="max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              <h2 className="text-xl font-semibold">Error Workflow Tester</h2>
              <Badge variant="outline" className="text-xs">Development Only</Badge>
            </div>
            {onClose && (
              <Button variant="ghost" size="sm" onClick={onClose}>
                ×
              </Button>
            )}
          </div>

          {/* Error Statistics */}
          {stats && (
            <div className="mb-6 p-4 bg-muted rounded-lg">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="h-4 w-4" />
                <h3 className="font-medium">Error Statistics</h3>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="font-medium">Total Errors</div>
                  <div className="text-2xl font-bold text-red-500">{stats.total}</div>
                </div>
                
                <div>
                  <div className="font-medium">By Type</div>
                  <div className="space-y-1">
                    {Object.entries(stats.byType).map(([type, count]) => (
                      <div key={type} className="flex justify-between">
                        <span className="capitalize">{type.replace('_', ' ')}</span>
                        <span>{count as number}</span>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div>
                  <div className="font-medium">By Severity</div>
                  <div className="space-y-1">
                    {Object.entries(stats.bySeverity).map(([severity, count]) => (
                      <div key={severity} className="flex justify-between">
                        <span className="capitalize">{severity}</span>
                        <span>{count as number}</span>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div>
                  <div className="font-medium">Recent Errors</div>
                  <div className="text-xs space-y-1">
                    {stats.recent.map((error: any, index: number) => (
                      <div key={index} className="truncate">
                        {error.type}: {error.message.substring(0, 30)}...
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Test Controls */}
          <div className="space-y-4">
            <h3 className="font-medium">Error Simulation Tests</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  () => ErrorTestingUtils.simulateApiError(500, 'Test API error'),
                  'API Error (500)'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                API Error (500)
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  () => ErrorTestingUtils.simulateApiError(404, 'Test not found error'),
                  'API Error (404)'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                API Error (404)
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  () => ErrorTestingUtils.simulateWebSocketError('Connection lost'),
                  'WebSocket Error'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                WebSocket Error
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  () => ErrorTestingUtils.simulateAIModelError('llama3', 'chat'),
                  'AI Model Error'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                AI Model Error
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  () => ErrorTestingUtils.simulatePipelineError(3, 'content_processing'),
                  'Pipeline Error'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                Pipeline Error
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  () => ErrorTestingUtils.simulateUIError('Component render failed'),
                  'UI Error'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                UI Error
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  ErrorTestingUtils.simulateRuntimeError,
                  'Runtime Error'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                Runtime Error
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => runErrorTest(
                  ErrorTestingUtils.simulatePromiseRejection,
                  'Promise Rejection'
                )}
                disabled={isRunning}
              >
                <Play className="h-3 w-3 mr-2" />
                Promise Rejection
              </Button>
            </div>

            <div className="flex gap-3 pt-4 border-t">
              <Button
                variant="outline"
                onClick={runRecoveryTest}
                disabled={isRunning}
              >
                <Play className="h-4 w-4 mr-2" />
                Test Recovery Actions
              </Button>
              
              <Button
                variant="outline"
                onClick={updateStats}
                disabled={isRunning}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                Refresh Stats
              </Button>
              
              <Button
                variant="destructive"
                onClick={clearAllErrors}
                disabled={isRunning}
              >
                Clear All Errors
              </Button>
            </div>
          </div>

          {/* Instructions */}
          <div className="mt-6 p-4 bg-blue-50/10 border border-blue-200 rounded-lg">
            <h4 className="font-medium text-blue-900 mb-2">Testing Instructions</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Click test buttons to simulate different error types</li>
              <li>• Check browser console for detailed error logs</li>
              <li>• Look for error notifications in the top-right corner</li>
              <li>• Test recovery actions when they appear</li>
              <li>• Use browser dev tools to inspect error service state</li>
            </ul>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}