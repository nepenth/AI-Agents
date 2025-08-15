import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react'
import { GlassCard } from '@/components/ui/GlassCard'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { errorService, ErrorRecoveryAction } from '@/services/errorService'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  recoveryActions: ErrorRecoveryAction[]
  isRecovering: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      recoveryActions: [],
      isRecovering: false
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Report error to error service
    errorService.reportError({
      type: 'ui_error',
      severity: 'high',
      message: error.message,
      details: {
        name: error.name,
        componentStack: errorInfo.componentStack
      },
      stack_trace: error.stack,
      context: {
        component: 'error_boundary',
        operation: 'component_error'
      }
    })

    // Get recovery actions
    const recoveryActions = errorService.getRecoveryActions({
      id: 'boundary_error',
      type: 'ui_error',
      severity: 'high',
      message: error.message,
      details: { name: error.name, componentStack: errorInfo.componentStack },
      stack_trace: error.stack,
      user_agent: navigator.userAgent,
      url: window.location.href,
      timestamp: new Date().toISOString(),
      session_id: 'current'
    })

    this.setState({
      errorInfo,
      recoveryActions
    })

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
  }

  handleRecoveryAction = async (action: ErrorRecoveryAction) => {
    this.setState({ isRecovering: true })
    
    try {
      await action.action()
      
      // If action succeeds, try to recover
      if (action.type === 'retry' || action.type === 'reset') {
        this.setState({
          hasError: false,
          error: null,
          errorInfo: null,
          recoveryActions: [],
          isRecovering: false
        })
      }
    } catch (recoveryError) {
      console.error('Recovery action failed:', recoveryError)
      // Show error message but don't reset the error boundary
      this.setState({ isRecovering: false })
    }
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background to-muted">
          <GlassCard className="max-w-2xl w-full p-8">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
                <AlertTriangle className="h-8 w-8 text-red-600" />
              </div>
              
              <h1 className="text-2xl font-bold text-foreground mb-2">
                Something went wrong
              </h1>
              
              <p className="text-muted-foreground mb-4">
                We encountered an unexpected error. Don't worry, we've been notified and are working on a fix.
              </p>
              
              <Badge variant="destructive" className="mb-4">
                {this.state.error?.name || 'Unknown Error'}
              </Badge>
            </div>

            {/* Error Details (Development Only) */}
            {import.meta.env?.DEV && this.state.error && (
              <div className="mb-6 p-4 bg-muted rounded-lg">
                <h3 className="font-medium text-foreground mb-2 flex items-center gap-2">
                  <Bug className="h-4 w-4" />
                  Error Details (Development)
                </h3>
                <div className="text-sm text-muted-foreground space-y-2">
                  <div>
                    <strong>Message:</strong> {this.state.error.message}
                  </div>
                  {this.state.error.stack && (
                    <div>
                      <strong>Stack Trace:</strong>
                      <pre className="mt-1 text-xs bg-background p-2 rounded overflow-x-auto">
                        {this.state.error.stack}
                      </pre>
                    </div>
                  )}
                  {this.state.errorInfo?.componentStack && (
                    <div>
                      <strong>Component Stack:</strong>
                      <pre className="mt-1 text-xs bg-background p-2 rounded overflow-x-auto">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Recovery Actions */}
            {this.state.recoveryActions.length > 0 && (
              <div className="mb-6">
                <h3 className="font-medium text-foreground mb-3">
                  Try these recovery options:
                </h3>
                <div className="space-y-2">
                  {this.state.recoveryActions.map((action) => (
                    <div key={action.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                      <div className="flex-1">
                        <div className="font-medium text-foreground">
                          {action.label}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {action.description}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => this.handleRecoveryAction(action)}
                        disabled={this.state.isRecovering}
                      >
                        {this.state.isRecovering ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          action.label
                        )}
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Default Actions */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                onClick={() => window.location.reload()}
                disabled={this.state.isRecovering}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Reload Page
              </Button>
              
              <Button
                variant="outline"
                onClick={() => window.location.href = '/'}
                disabled={this.state.isRecovering}
              >
                <Home className="h-4 w-4 mr-2" />
                Go Home
              </Button>
            </div>

            {/* Additional Help */}
            <div className="mt-6 pt-6 border-t border-border text-center">
              <p className="text-sm text-muted-foreground mb-2">
                If the problem persists, please contact support with the error details above.
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const errorData = {
                    message: this.state.error?.message,
                    stack: this.state.error?.stack,
                    componentStack: this.state.errorInfo?.componentStack,
                    url: window.location.href,
                    userAgent: navigator.userAgent,
                    timestamp: new Date().toISOString()
                  }
                  
                  const subject = encodeURIComponent('Frontend Error Report')
                  const body = encodeURIComponent(`Error Details:\n${JSON.stringify(errorData, null, 2)}`)
                  window.open(`mailto:support@example.com?subject=${subject}&body=${body}`)
                }}
              >
                Report This Error
              </Button>
            </div>
          </GlassCard>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook version for functional components
export function useErrorBoundary() {
  const [error, setError] = React.useState<Error | null>(null)

  const resetError = React.useCallback(() => {
    setError(null)
  }, [])

  const captureError = React.useCallback((error: Error) => {
    setError(error)
  }, [])

  React.useEffect(() => {
    if (error) {
      throw error
    }
  }, [error])

  return { captureError, resetError }
}