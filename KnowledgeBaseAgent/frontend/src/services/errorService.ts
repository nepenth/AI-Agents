import { apiService } from './api'

export interface ErrorReport {
  id: string
  type: 'api_error' | 'websocket_error' | 'ai_model_error' | 'pipeline_error' | 'ui_error'
  severity: 'low' | 'medium' | 'high' | 'critical'
  message: string
  details: Record<string, any>
  stack_trace?: string
  user_agent: string
  url: string
  timestamp: string
  user_id?: string
  session_id: string
}

export interface ErrorRecoveryAction {
  id: string
  label: string
  description: string
  action: () => Promise<void> | void
  type: 'retry' | 'fallback' | 'redirect' | 'reset' | 'contact_support'
}

export interface ErrorContext {
  component?: string
  operation?: string
  data?: Record<string, any>
  user_action?: string
}

export class ErrorService {
  private errorQueue: ErrorReport[] = []
  private sessionId: string
  private maxQueueSize = 100
  private reportingEnabled = true

  constructor() {
    this.sessionId = this.generateSessionId()
    this.setupGlobalErrorHandlers()
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
  }

  private setupGlobalErrorHandlers(): void {
    // Handle unhandled JavaScript errors
    window.addEventListener('error', (event) => {
      this.reportError({
        type: 'ui_error',
        severity: 'high',
        message: event.message,
        details: {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
          error: event.error?.toString()
        },
        stack_trace: event.error?.stack,
        context: { component: 'global', operation: 'runtime_error' }
      })
    })

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.reportError({
        type: 'ui_error',
        severity: 'high',
        message: `Unhandled promise rejection: ${event.reason}`,
        details: {
          reason: event.reason?.toString(),
          promise: event.promise
        },
        stack_trace: event.reason?.stack,
        context: { component: 'global', operation: 'promise_rejection' }
      })
    })
  }

  async reportError(error: {
    type: ErrorReport['type']
    severity: ErrorReport['severity']
    message: string
    details?: Record<string, any>
    stack_trace?: string
    context?: ErrorContext
  }): Promise<void> {
    const errorReport: ErrorReport = {
      id: `error_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
      type: error.type,
      severity: error.severity,
      message: error.message,
      details: {
        ...error.details,
        context: error.context
      },
      stack_trace: error.stack_trace,
      user_agent: navigator.userAgent,
      url: window.location.href,
      timestamp: new Date().toISOString(),
      session_id: this.sessionId
    }

    // Add to local queue
    this.addToQueue(errorReport)

    // Report to backend if enabled
    if (this.reportingEnabled) {
      try {
        await this.sendErrorReport(errorReport)
      } catch (reportingError) {
        console.error('Failed to report error:', reportingError)
        // Don't create infinite loop by reporting the reporting error
      }
    }

    // Log to console in development
    if (import.meta.env?.DEV) {
      console.error('Error reported:', errorReport)
    }
  }

  private addToQueue(error: ErrorReport): void {
    this.errorQueue.unshift(error)
    
    // Maintain queue size
    if (this.errorQueue.length > this.maxQueueSize) {
      this.errorQueue = this.errorQueue.slice(0, this.maxQueueSize)
    }
  }

  private async sendErrorReport(error: ErrorReport): Promise<void> {
    try {
      const { apiService } = await import('./api')
      await apiService.post('/system/errors/report', error)
    } catch (err) {
      // Store in localStorage as fallback
      this.storeErrorLocally(error)
    }
  }

  private storeErrorLocally(error: ErrorReport): void {
    try {
      const storedErrors = JSON.parse(localStorage.getItem('error_reports') || '[]')
      storedErrors.unshift(error)
      
      // Keep only last 50 errors in localStorage
      const trimmedErrors = storedErrors.slice(0, 50)
      localStorage.setItem('error_reports', JSON.stringify(trimmedErrors))
    } catch (err) {
      console.error('Failed to store error locally:', err)
    }
  }

  getRecentErrors(limit = 20): ErrorReport[] {
    return this.errorQueue.slice(0, limit)
  }

  getErrorsByType(type: ErrorReport['type']): ErrorReport[] {
    return this.errorQueue.filter(error => error.type === type)
  }

  getErrorsBySeverity(severity: ErrorReport['severity']): ErrorReport[] {
    return this.errorQueue.filter(error => error.severity === severity)
  }

  clearErrors(): void {
    this.errorQueue = []
    localStorage.removeItem('error_reports')
  }

  setReportingEnabled(enabled: boolean): void {
    this.reportingEnabled = enabled
  }

  // Error recovery actions
  getRecoveryActions(error: ErrorReport): ErrorRecoveryAction[] {
    const actions: ErrorRecoveryAction[] = []

    switch (error.type) {
      case 'api_error':
        actions.push({
          id: 'retry_request',
          label: 'Retry Request',
          description: 'Attempt the failed request again',
          action: () => this.retryLastRequest(error),
          type: 'retry'
        })
        
        if (error.details.status >= 500) {
          actions.push({
            id: 'check_server_status',
            label: 'Check Server Status',
            description: 'Verify if the server is responding',
            action: () => this.checkServerHealth(),
            type: 'fallback'
          })
        }
        break

      case 'websocket_error':
        actions.push({
          id: 'reconnect_websocket',
          label: 'Reconnect',
          description: 'Attempt to reconnect to the server',
          action: () => this.reconnectWebSocket(),
          type: 'retry'
        })
        break

      case 'ai_model_error':
        actions.push({
          id: 'test_model_connection',
          label: 'Test Model Connection',
          description: 'Check if the AI model is accessible',
          action: () => this.testModelConnection(error.details.model),
          type: 'fallback'
        })
        
        actions.push({
          id: 'use_fallback_model',
          label: 'Use Fallback Model',
          description: 'Switch to a backup AI model',
          action: () => this.useFallbackModel(error.details.phase),
          type: 'fallback'
        })
        break

      case 'pipeline_error':
        actions.push({
          id: 'reset_pipeline_phase',
          label: 'Reset Phase',
          description: 'Reset the failed pipeline phase',
          action: () => this.resetPipelinePhase(error.details.phase),
          type: 'reset'
        })
        
        actions.push({
          id: 'skip_phase',
          label: 'Skip Phase',
          description: 'Skip the failed phase and continue',
          action: () => this.skipPipelinePhase(error.details.phase),
          type: 'fallback'
        })
        break

      case 'ui_error':
        actions.push({
          id: 'refresh_page',
          label: 'Refresh Page',
          description: 'Reload the current page',
          action: () => window.location.reload(),
          type: 'reset'
        })
        
        actions.push({
          id: 'clear_cache',
          label: 'Clear Cache',
          description: 'Clear browser cache and reload',
          action: () => this.clearCacheAndReload(),
          type: 'reset'
        })
        break
    }

    // Always add contact support option for critical errors
    if (error.severity === 'critical') {
      actions.push({
        id: 'contact_support',
        label: 'Contact Support',
        description: 'Report this issue to technical support',
        action: () => this.contactSupport(error),
        type: 'contact_support'
      })
    }

    return actions
  }

  // Recovery action implementations
  private async retryLastRequest(error: ErrorReport): Promise<void> {
    if (error.details.url && error.details.method) {
      try {
        const { apiService } = await import('./api')
        const response = await fetch(error.details.url, {
          method: error.details.method,
          headers: { 'Content-Type': 'application/json' },
          body: error.details.data ? JSON.stringify(error.details.data) : undefined
        })
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
      } catch (retryError) {
        throw new Error('Retry failed: ' + retryError)
      }
    }
  }

  private async checkServerHealth(): Promise<void> {
    try {
      const { apiService } = await import('./api')
      await apiService.get('/system/health')
    } catch (error) {
      throw new Error('Server health check failed')
    }
  }

  private async reconnectWebSocket(): Promise<void> {
    // This would be implemented by the WebSocket service
    const { websocketService } = await import('./websocket')
    await websocketService.connect()
  }

  private async testModelConnection(modelName: string): Promise<void> {
    try {
      const { aiModelService } = await import('./aiModelService')
      await aiModelService.testModel(modelName, 'chat', {})
    } catch (error) {
      throw new Error(`Model connection test failed: ${error}`)
    }
  }

  private async useFallbackModel(phase: string): Promise<void> {
    try {
      const { aiModelService } = await import('./aiModelService')
      await aiModelService.setFallbackModel(phase)
    } catch (error) {
      throw new Error(`Failed to switch to fallback model: ${error}`)
    }
  }

  private async resetPipelinePhase(phase: string): Promise<void> {
    try {
      const { pipelineService } = await import('./pipelineService')
      await pipelineService.resetPhase(parseInt(phase))
    } catch (error) {
      throw new Error(`Failed to reset pipeline phase: ${error}`)
    }
  }

  private async skipPipelinePhase(phase: string): Promise<void> {
    try {
      const { pipelineService } = await import('./pipelineService')
      await pipelineService.skipPhase(parseInt(phase))
    } catch (error) {
      throw new Error(`Failed to skip pipeline phase: ${error}`)
    }
  }

  private async clearCacheAndReload(): Promise<void> {
    if ('caches' in window) {
      const cacheNames = await caches.keys()
      await Promise.all(cacheNames.map(name => caches.delete(name)))
    }
    
    localStorage.clear()
    sessionStorage.clear()
    window.location.reload()
  }

  private async contactSupport(error: ErrorReport): Promise<void> {
    const supportData = {
      error_id: error.id,
      error_type: error.type,
      severity: error.severity,
      message: error.message,
      user_agent: error.user_agent,
      url: error.url,
      timestamp: error.timestamp
    }

    try {
      const { apiService } = await import('./api')
      await apiService.post('/system/support/report', supportData)
    } catch (err) {
      // Fallback to mailto
      const subject = encodeURIComponent(`Error Report: ${error.type} - ${error.severity}`)
      const body = encodeURIComponent(`Error Details:\n${JSON.stringify(supportData, null, 2)}`)
      window.open(`mailto:support@example.com?subject=${subject}&body=${body}`)
    }
  }
}

export const errorService = new ErrorService()

// Error boundary hook
export function useErrorHandler() {
  const reportError = (error: Error, errorInfo?: { componentStack: string }) => {
    errorService.reportError({
      type: 'ui_error',
      severity: 'high',
      message: error.message,
      details: {
        name: error.name,
        componentStack: errorInfo?.componentStack
      },
      stack_trace: error.stack,
      context: {
        component: 'error_boundary',
        operation: 'component_error'
      }
    })
  }

  const reportApiError = (error: any, context?: ErrorContext) => {
    errorService.reportError({
      type: 'api_error',
      severity: error.status >= 500 ? 'critical' : 'medium',
      message: error.message || 'API request failed',
      details: {
        status: error.status,
        statusText: error.statusText,
        url: error.config?.url,
        method: error.config?.method,
        data: error.config?.data
      },
      context
    })
  }

  const reportModelError = (error: any, modelName: string, phase: string) => {
    errorService.reportError({
      type: 'ai_model_error',
      severity: 'high',
      message: `AI model error: ${error.message}`,
      details: {
        model: modelName,
        phase,
        error_type: error.name
      },
      stack_trace: error.stack,
      context: {
        component: 'ai_model',
        operation: 'model_request'
      }
    })
  }

  const reportPipelineError = (error: any, phase: number, operation: string) => {
    errorService.reportError({
      type: 'pipeline_error',
      severity: 'critical',
      message: `Pipeline phase ${phase} failed: ${error.message}`,
      details: {
        phase: phase.toString(),
        operation,
        error_type: error.name
      },
      stack_trace: error.stack,
      context: {
        component: 'pipeline',
        operation
      }
    })
  }

  return {
    reportError,
    reportApiError,
    reportModelError,
    reportPipelineError,
    getRecoveryActions: errorService.getRecoveryActions.bind(errorService),
    getRecentErrors: errorService.getRecentErrors.bind(errorService)
  }
}