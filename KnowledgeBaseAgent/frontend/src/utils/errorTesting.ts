import { errorService } from '@/services/errorService'

/**
 * Error testing utilities for development and testing environments
 */
export class ErrorTestingUtils {
  /**
   * Simulate different types of errors for testing error handling
   */
  static simulateApiError(status = 500, message = 'Simulated API error') {
    errorService.reportError({
      type: 'api_error',
      severity: status >= 500 ? 'critical' : 'medium',
      message,
      details: {
        status,
        url: '/api/test',
        method: 'GET',
        simulated: true
      },
      context: {
        component: 'error_testing',
        operation: 'simulate_api_error'
      }
    })
  }

  static simulateWebSocketError(message = 'Simulated WebSocket error') {
    errorService.reportError({
      type: 'websocket_error',
      severity: 'high',
      message,
      details: {
        connection_state: 'disconnected',
        simulated: true
      },
      context: {
        component: 'error_testing',
        operation: 'simulate_websocket_error'
      }
    })
  }

  static simulateAIModelError(modelName = 'test-model', phase = 'chat') {
    errorService.reportError({
      type: 'ai_model_error',
      severity: 'high',
      message: `AI model ${modelName} failed`,
      details: {
        model: modelName,
        phase,
        simulated: true
      },
      context: {
        component: 'error_testing',
        operation: 'simulate_ai_model_error'
      }
    })
  }

  static simulatePipelineError(phase = 1, operation = 'test_operation') {
    errorService.reportError({
      type: 'pipeline_error',
      severity: 'critical',
      message: `Pipeline phase ${phase} failed`,
      details: {
        phase: phase.toString(),
        operation,
        simulated: true
      },
      context: {
        component: 'error_testing',
        operation: 'simulate_pipeline_error'
      }
    })
  }

  static simulateUIError(message = 'Simulated UI error') {
    errorService.reportError({
      type: 'ui_error',
      severity: 'medium',
      message,
      details: {
        simulated: true
      },
      context: {
        component: 'error_testing',
        operation: 'simulate_ui_error'
      }
    })
  }

  /**
   * Simulate a JavaScript runtime error
   */
  static simulateRuntimeError() {
    // This will trigger the global error handler
    setTimeout(() => {
      throw new Error('Simulated runtime error for testing')
    }, 100)
  }

  /**
   * Simulate an unhandled promise rejection
   */
  static simulatePromiseRejection() {
    // This will trigger the unhandled rejection handler
    Promise.reject(new Error('Simulated promise rejection for testing'))
  }

  /**
   * Test error recovery actions
   */
  static async testRecoveryActions() {
    const testError = {
      id: 'test_error',
      type: 'api_error' as const,
      severity: 'medium' as const,
      message: 'Test error for recovery testing',
      details: {
        status: 500,
        url: '/api/test',
        method: 'GET'
      },
      stack_trace: 'Test stack trace',
      user_agent: navigator.userAgent,
      url: window.location.href,
      timestamp: new Date().toISOString(),
      session_id: 'test_session'
    }

    const recoveryActions = errorService.getRecoveryActions(testError)
    console.log('Available recovery actions:', recoveryActions)

    return recoveryActions
  }

  /**
   * Clear all test errors
   */
  static clearTestErrors() {
    errorService.clearErrors()
  }

  /**
   * Get error statistics for testing
   */
  static getErrorStats() {
    const recentErrors = errorService.getRecentErrors(100)
    
    const stats = {
      total: recentErrors.length,
      byType: {} as Record<string, number>,
      bySeverity: {} as Record<string, number>,
      recent: recentErrors.slice(0, 5)
    }

    recentErrors.forEach(error => {
      stats.byType[error.type] = (stats.byType[error.type] || 0) + 1
      stats.bySeverity[error.severity] = (stats.bySeverity[error.severity] || 0) + 1
    })

    return stats
  }
}

// Development-only error testing interface
if (import.meta.env?.DEV) {
  // Make error testing utilities available in development console
  ;(window as any).errorTesting = ErrorTestingUtils
  
  console.log('Error testing utilities available at window.errorTesting')
  console.log('Available methods:')
  console.log('- errorTesting.simulateApiError(status, message)')
  console.log('- errorTesting.simulateWebSocketError(message)')
  console.log('- errorTesting.simulateAIModelError(modelName, phase)')
  console.log('- errorTesting.simulatePipelineError(phase, operation)')
  console.log('- errorTesting.simulateUIError(message)')
  console.log('- errorTesting.simulateRuntimeError()')
  console.log('- errorTesting.simulatePromiseRejection()')
  console.log('- errorTesting.testRecoveryActions()')
  console.log('- errorTesting.clearTestErrors()')
  console.log('- errorTesting.getErrorStats()')
}