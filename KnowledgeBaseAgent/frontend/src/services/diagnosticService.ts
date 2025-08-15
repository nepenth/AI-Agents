import { apiService } from './api'
import { aiModelService } from './aiModelService'
import { pipelineService } from './pipelineService'
import { websocketService } from './websocket'

export interface DiagnosticResult {
  id: string
  name: string
  status: 'passed' | 'failed' | 'warning'
  message: string
  details?: Record<string, any>
  metrics?: Record<string, number>
  duration: number
  timestamp: string
  recommendations?: string[]
}

export interface SystemInfo {
  browser: {
    name: string
    version: string
    userAgent: string
  }
  screen: {
    width: number
    height: number
    pixelRatio: number
  }
  memory: {
    used?: number
    total?: number
    limit?: number
  }
  connection: {
    type?: string
    effectiveType?: string
    downlink?: number
    rtt?: number
  }
  performance: {
    navigation: PerformanceNavigationTiming | null
    memory?: any
  }
}

export class DiagnosticService {
  private testResults: Map<string, DiagnosticResult> = new Map()

  async runSystemHealthCheck(): Promise<DiagnosticResult> {
    const startTime = performance.now()
    
    try {
      const systemInfo = this.getSystemInfo()
      const memoryUsage = this.getMemoryUsage()
      const performanceMetrics = this.getPerformanceMetrics()
      
      const issues: string[] = []
      const recommendations: string[] = []
      
      // Check memory usage
      if (memoryUsage.used && memoryUsage.total) {
        const memoryPercent = (memoryUsage.used / memoryUsage.total) * 100
        if (memoryPercent > 80) {
          issues.push('High memory usage detected')
          recommendations.push('Close unused browser tabs to free up memory')
        }
      }
      
      // Check screen resolution
      if (systemInfo.screen.width < 1024) {
        recommendations.push('Consider using a larger screen for better dashboard experience')
      }
      
      // Check connection quality
      if (systemInfo.connection.effectiveType && ['slow-2g', '2g'].includes(systemInfo.connection.effectiveType)) {
        issues.push('Slow network connection detected')
        recommendations.push('Consider switching to a faster internet connection')
      }
      
      const status = issues.length > 0 ? 'warning' : 'passed'
      const message = issues.length > 0 
        ? `System health check completed with ${issues.length} issue(s)`
        : 'System health check passed - all metrics within normal ranges'
      
      const result: DiagnosticResult = {
        id: 'system-health',
        name: 'System Health Check',
        status,
        message,
        details: {
          browser: systemInfo.browser,
          screen: systemInfo.screen,
          memory: memoryUsage,
          connection: systemInfo.connection,
          issues
        },
        metrics: {
          memory_usage_mb: memoryUsage.used || 0,
          screen_width: systemInfo.screen.width,
          screen_height: systemInfo.screen.height,
          connection_rtt: systemInfo.connection.rtt || 0
        },
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations
      }
      
      this.testResults.set(result.id, result)
      return result
      
    } catch (error) {
      const result: DiagnosticResult = {
        id: 'system-health',
        name: 'System Health Check',
        status: 'failed',
        message: `System health check failed: ${error}`,
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString()
      }
      
      this.testResults.set(result.id, result)
      return result
    }
  }

  async runNetworkConnectivityTest(): Promise<DiagnosticResult> {
    const startTime = performance.now()
    
    try {
      // Test API connectivity
      const apiStartTime = performance.now()
      await apiService.get('/system/health')
      const apiResponseTime = performance.now() - apiStartTime
      
      // Test WebSocket connectivity
      const wsConnected = websocketService.isConnected()
      
      // Test external connectivity (if needed)
      const externalStartTime = performance.now()
      const externalResponse = await fetch('https://httpbin.org/get', { 
        method: 'GET',
        mode: 'cors'
      }).catch(() => null)
      const externalResponseTime = externalResponse ? performance.now() - externalStartTime : null
      
      const issues: string[] = []
      const recommendations: string[] = []
      
      if (apiResponseTime > 5000) {
        issues.push('Slow API response time')
        recommendations.push('Check server performance or network connection')
      }
      
      if (!wsConnected) {
        issues.push('WebSocket connection not established')
        recommendations.push('Check WebSocket server availability')
      }
      
      if (!externalResponse) {
        issues.push('External connectivity test failed')
        recommendations.push('Check internet connection and firewall settings')
      }
      
      const status = issues.length > 0 ? 'warning' : 'passed'
      const message = issues.length > 0 
        ? `Network connectivity test completed with ${issues.length} issue(s)`
        : 'Network connectivity test passed - all connections healthy'
      
      const result: DiagnosticResult = {
        id: 'network-connectivity',
        name: 'Network Connectivity Test',
        status,
        message,
        details: {
          api_connected: true,
          websocket_connected: wsConnected,
          external_connected: !!externalResponse,
          issues
        },
        metrics: {
          api_response_time_ms: Math.round(apiResponseTime),
          external_response_time_ms: externalResponseTime ? Math.round(externalResponseTime) : 0
        },
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations
      }
      
      this.testResults.set(result.id, result)
      return result
      
    } catch (error) {
      const result: DiagnosticResult = {
        id: 'network-connectivity',
        name: 'Network Connectivity Test',
        status: 'failed',
        message: `Network connectivity test failed: ${error}`,
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations: ['Check network connection and server availability']
      }
      
      this.testResults.set(result.id, result)
      return result
    }
  }

  async runAIModelTest(): Promise<DiagnosticResult> {
    const startTime = performance.now()
    
    try {
      // Get available models
      const availableModels = await aiModelService.getAvailableModels()
      
      // Test model connectivity
      const modelTests = []
      for (const [backend, models] of Object.entries(availableModels)) {
        for (const model of models) {
          try {
            const testStartTime = performance.now()
            await aiModelService.testModel(model, 'chat', { max_tokens: 10 })
            const testDuration = performance.now() - testStartTime
            
            modelTests.push({
              backend,
              model,
              status: 'passed',
              response_time: testDuration
            })
          } catch (error) {
            modelTests.push({
              backend,
              model,
              status: 'failed',
              error: String(error)
            })
          }
        }
      }
      
      const passedTests = modelTests.filter(t => t.status === 'passed')
      const failedTests = modelTests.filter(t => t.status === 'failed')
      
      const issues: string[] = []
      const recommendations: string[] = []
      
      if (failedTests.length > 0) {
        issues.push(`${failedTests.length} AI model(s) failed connectivity test`)
        recommendations.push('Check AI service configuration and availability')
      }
      
      if (passedTests.length === 0) {
        issues.push('No AI models are accessible')
        recommendations.push('Verify AI service is running and properly configured')
      }
      
      const avgResponseTime = passedTests.length > 0 
        ? passedTests.reduce((sum, test) => sum + test.response_time, 0) / passedTests.length
        : 0
      
      if (avgResponseTime > 10000) {
        issues.push('Slow AI model response times')
        recommendations.push('Consider using faster models or check system resources')
      }
      
      const status = failedTests.length > 0 ? 'warning' : 'passed'
      const message = `AI model test completed - ${passedTests.length} passed, ${failedTests.length} failed`
      
      const result: DiagnosticResult = {
        id: 'ai-models',
        name: 'AI Model Connectivity Test',
        status,
        message,
        details: {
          total_models: modelTests.length,
          passed_models: passedTests.length,
          failed_models: failedTests.length,
          model_tests: modelTests,
          issues
        },
        metrics: {
          total_models: modelTests.length,
          passed_models: passedTests.length,
          failed_models: failedTests.length,
          avg_response_time_ms: Math.round(avgResponseTime)
        },
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations
      }
      
      this.testResults.set(result.id, result)
      return result
      
    } catch (error) {
      const result: DiagnosticResult = {
        id: 'ai-models',
        name: 'AI Model Connectivity Test',
        status: 'failed',
        message: `AI model test failed: ${error}`,
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations: ['Check AI service configuration and network connectivity']
      }
      
      this.testResults.set(result.id, result)
      return result
    }
  }

  async runPipelineIntegrityTest(): Promise<DiagnosticResult> {
    const startTime = performance.now()
    
    try {
      // Get pipeline status
      const pipelineStatus = await pipelineService.getStatus()
      
      // Test each phase
      const phaseTests = []
      for (let phase = 1; phase <= 7; phase++) {
        try {
          const phaseStatus = await pipelineService.getPhaseStatus(phase)
          phaseTests.push({
            phase,
            status: 'passed',
            last_run: phaseStatus.lastRun,
            duration: phaseStatus.duration
          })
        } catch (error) {
          phaseTests.push({
            phase,
            status: 'failed',
            error: String(error)
          })
        }
      }
      
      const passedPhases = phaseTests.filter(t => t.status === 'passed')
      const failedPhases = phaseTests.filter(t => t.status === 'failed')
      
      const issues: string[] = []
      const recommendations: string[] = []
      
      if (failedPhases.length > 0) {
        issues.push(`${failedPhases.length} pipeline phase(s) have issues`)
        recommendations.push('Check pipeline configuration and dependencies')
      }
      
      const status = failedPhases.length > 0 ? 'warning' : 'passed'
      const message = `Pipeline integrity test completed - ${passedPhases.length}/7 phases healthy`
      
      const result: DiagnosticResult = {
        id: 'pipeline-integrity',
        name: 'Pipeline Integrity Test',
        status,
        message,
        details: {
          total_phases: 7,
          healthy_phases: passedPhases.length,
          failed_phases: failedPhases.length,
          phase_tests: phaseTests,
          pipeline_status: pipelineStatus,
          issues
        },
        metrics: {
          total_phases: 7,
          healthy_phases: passedPhases.length,
          failed_phases: failedPhases.length
        },
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations
      }
      
      this.testResults.set(result.id, result)
      return result
      
    } catch (error) {
      const result: DiagnosticResult = {
        id: 'pipeline-integrity',
        name: 'Pipeline Integrity Test',
        status: 'failed',
        message: `Pipeline integrity test failed: ${error}`,
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations: ['Check pipeline service availability and configuration']
      }
      
      this.testResults.set(result.id, result)
      return result
    }
  }

  async runConfigurationValidation(): Promise<DiagnosticResult> {
    const startTime = performance.now()
    
    try {
      const issues: string[] = []
      const recommendations: string[] = []
      const configChecks: Record<string, any> = {}
      
      // Check environment variables
      const requiredEnvVars = ['VITE_API_URL', 'VITE_WS_URL']
      for (const envVar of requiredEnvVars) {
        const value = import.meta.env[envVar]
        configChecks[envVar] = !!value
        if (!value) {
          issues.push(`Missing environment variable: ${envVar}`)
          recommendations.push(`Set ${envVar} in your environment configuration`)
        }
      }
      
      // Check localStorage availability
      try {
        localStorage.setItem('test', 'test')
        localStorage.removeItem('test')
        configChecks.localStorage = true
      } catch (error) {
        configChecks.localStorage = false
        issues.push('localStorage is not available')
        recommendations.push('Enable localStorage in browser settings')
      }
      
      // Check sessionStorage availability
      try {
        sessionStorage.setItem('test', 'test')
        sessionStorage.removeItem('test')
        configChecks.sessionStorage = true
      } catch (error) {
        configChecks.sessionStorage = false
        issues.push('sessionStorage is not available')
        recommendations.push('Enable sessionStorage in browser settings')
      }
      
      // Check WebSocket support
      configChecks.webSocketSupport = 'WebSocket' in window
      if (!configChecks.webSocketSupport) {
        issues.push('WebSocket is not supported')
        recommendations.push('Use a modern browser that supports WebSocket')
      }
      
      // Check Service Worker support
      configChecks.serviceWorkerSupport = 'serviceWorker' in navigator
      
      const status = issues.length > 0 ? 'warning' : 'passed'
      const message = issues.length > 0 
        ? `Configuration validation completed with ${issues.length} issue(s)`
        : 'Configuration validation passed - all settings are valid'
      
      const result: DiagnosticResult = {
        id: 'configuration-validation',
        name: 'Configuration Validation',
        status,
        message,
        details: {
          config_checks: configChecks,
          issues
        },
        metrics: {
          total_checks: Object.keys(configChecks).length,
          passed_checks: Object.values(configChecks).filter(Boolean).length,
          failed_checks: Object.values(configChecks).filter(v => !v).length
        },
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString(),
        recommendations
      }
      
      this.testResults.set(result.id, result)
      return result
      
    } catch (error) {
      const result: DiagnosticResult = {
        id: 'configuration-validation',
        name: 'Configuration Validation',
        status: 'failed',
        message: `Configuration validation failed: ${error}`,
        duration: performance.now() - startTime,
        timestamp: new Date().toISOString()
      }
      
      this.testResults.set(result.id, result)
      return result
    }
  }

  getSystemInfo(): SystemInfo {
    const nav = navigator as any
    
    return {
      browser: {
        name: this.getBrowserName(),
        version: this.getBrowserVersion(),
        userAgent: navigator.userAgent
      },
      screen: {
        width: screen.width,
        height: screen.height,
        pixelRatio: window.devicePixelRatio
      },
      memory: {
        used: (performance as any).memory?.usedJSHeapSize,
        total: (performance as any).memory?.totalJSHeapSize,
        limit: (performance as any).memory?.jsHeapSizeLimit
      },
      connection: {
        type: nav.connection?.type,
        effectiveType: nav.connection?.effectiveType,
        downlink: nav.connection?.downlink,
        rtt: nav.connection?.rtt
      },
      performance: {
        navigation: performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming,
        memory: (performance as any).memory
      }
    }
  }

  private getBrowserName(): string {
    const userAgent = navigator.userAgent
    if (userAgent.includes('Chrome')) return 'Chrome'
    if (userAgent.includes('Firefox')) return 'Firefox'
    if (userAgent.includes('Safari')) return 'Safari'
    if (userAgent.includes('Edge')) return 'Edge'
    return 'Unknown'
  }

  private getBrowserVersion(): string {
    const userAgent = navigator.userAgent
    const match = userAgent.match(/(Chrome|Firefox|Safari|Edge)\/(\d+)/)
    return match ? match[2] : 'Unknown'
  }

  private getMemoryUsage() {
    const memory = (performance as any).memory
    return {
      used: memory?.usedJSHeapSize,
      total: memory?.totalJSHeapSize,
      limit: memory?.jsHeapSizeLimit
    }
  }

  private getPerformanceMetrics() {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
    return {
      domContentLoaded: navigation?.domContentLoadedEventEnd - navigation?.domContentLoadedEventStart,
      loadComplete: navigation?.loadEventEnd - navigation?.loadEventStart,
      firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime,
      firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime
    }
  }

  getTestResult(testId: string): DiagnosticResult | undefined {
    return this.testResults.get(testId)
  }

  getAllTestResults(): DiagnosticResult[] {
    return Array.from(this.testResults.values())
  }

  clearTestResults(): void {
    this.testResults.clear()
  }
}

export const diagnosticService = new DiagnosticService()