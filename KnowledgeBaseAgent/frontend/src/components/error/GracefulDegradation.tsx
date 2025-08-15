import React, { useState, useEffect } from 'react'
import { AlertTriangle, Wifi, WifiOff, Zap, ZapOff, Database, DatabaseZap, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useRealTimeUpdates } from '@/hooks/useRealTimeUpdates'
import { cn } from '@/utils/cn'

interface ServiceStatus {
  api: 'online' | 'offline' | 'degraded'
  websocket: 'connected' | 'disconnected' | 'reconnecting'
  ai_models: 'available' | 'unavailable' | 'partial'
  database: 'healthy' | 'slow' | 'error'
}

interface GracefulDegradationProps {
  children: React.ReactNode
  fallbackComponent?: React.ReactNode
  showStatusBar?: boolean
}

export function GracefulDegradation({
  children,
  fallbackComponent,
  showStatusBar = true
}: GracefulDegradationProps) {
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({
    api: 'online',
    websocket: 'connected',
    ai_models: 'available',
    database: 'healthy'
  })
  
  const [degradationMode, setDegradationMode] = useState<'none' | 'partial' | 'offline'>('none')
  const [userPreferences, setUserPreferences] = useState({
    enableOfflineMode: true,
    showDegradationWarnings: true,
    autoRetry: true
  })

  // Monitor service health
  const systemHealth = useRealTimeUpdates('system.health')

  useEffect(() => {
    if (systemHealth.lastUpdate) {
      const healthData = systemHealth.lastUpdate
      const newStatus: ServiceStatus = {
        api: (healthData as any).api_status || 'offline',
        websocket: systemHealth.isConnected ? 'connected' : 'disconnected',
        ai_models: (healthData as any).ai_models_status || 'unavailable',
        database: (healthData as any).database_status || 'error'
      }

      setServiceStatus(newStatus)

      // Determine degradation mode
      const criticalServicesDown = newStatus.api === 'offline' || newStatus.database === 'error'
      const partialServicesDown = newStatus.websocket === 'disconnected' || newStatus.ai_models === 'unavailable'

      if (criticalServicesDown) {
        setDegradationMode('offline')
      } else if (partialServicesDown) {
        setDegradationMode('partial')
      } else {
        setDegradationMode('none')
      }
    }
  }, [systemHealth])

  const getServiceIcon = (service: keyof ServiceStatus) => {
    const status = serviceStatus[service]
    
    switch (service) {
      case 'api':
        return status === 'online' ? 
          <Database className="h-4 w-4 text-green-500" /> : 
          <DatabaseZap className="h-4 w-4 text-red-500" />
      
      case 'websocket':
        return status === 'connected' ? 
          <Wifi className="h-4 w-4 text-green-500" /> : 
          <WifiOff className="h-4 w-4 text-red-500" />
      
      case 'ai_models':
        return status === 'available' ? 
          <Zap className="h-4 w-4 text-green-500" /> : 
          <ZapOff className="h-4 w-4 text-red-500" />
      
      case 'database':
        return status === 'healthy' ? 
          <Database className="h-4 w-4 text-green-500" /> : 
          <Database className="h-4 w-4 text-red-500" />
      
      default:
        return null
    }
  }

  const getServiceStatus = (service: keyof ServiceStatus) => {
    const status = serviceStatus[service]
    
    switch (status) {
      case 'online':
      case 'connected':
      case 'available':
      case 'healthy':
        return 'healthy'
      case 'degraded':
      case 'reconnecting':
      case 'partial':
      case 'slow':
        return 'warning'
      default:
        return 'critical'
    }
  }

  // Render offline fallback
  if (degradationMode === 'offline' && fallbackComponent) {
    return (
      <div className="min-h-screen flex flex-col">
        {showStatusBar && <ServiceStatusBar serviceStatus={serviceStatus} />}
        <div className="flex-1 flex items-center justify-center p-4">
          {fallbackComponent}
        </div>
      </div>
    )
  }

  // Render with degradation warnings
  return (
    <div className="min-h-screen flex flex-col">
      {showStatusBar && <ServiceStatusBar serviceStatus={serviceStatus} />}
      
      {degradationMode !== 'none' && userPreferences.showDegradationWarnings && (
        <DegradationWarning
          mode={degradationMode}
          serviceStatus={serviceStatus}
          onDismiss={() => setUserPreferences(prev => ({ ...prev, showDegradationWarnings: false }))}
        />
      )}
      
      <div className="flex-1">
        {children}
      </div>
    </div>
  )
}

interface ServiceStatusBarProps {
  serviceStatus: ServiceStatus
}

function ServiceStatusBar({ serviceStatus }: ServiceStatusBarProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  const hasIssues = Object.values(serviceStatus).some(status => 
    !['online', 'connected', 'available', 'healthy'].includes(status)
  )

  if (!hasIssues) {
    return null // Don't show status bar when everything is healthy
  }

  return (
    <div className="bg-muted border-b border-border">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              <span className="text-sm font-medium">
                System Status
              </span>
            </div>
            
            <div className="flex items-center gap-3">
              {Object.entries(serviceStatus).map(([service, status]) => {
                const serviceKey = service as keyof ServiceStatus
                return (
                  <div key={service} className="flex items-center gap-1">
                    {getServiceIcon(serviceKey)}
                    <StatusBadge 
                      status={getServiceStatus(serviceKey)} 
                      size="sm"
                    />
                  </div>
                )
              })}
            </div>
          </div>
          
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? 'Hide Details' : 'Show Details'}
          </Button>
        </div>
        
        {isExpanded && (
          <div className="pb-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {Object.entries(serviceStatus).map(([service, status]) => (
                <div key={service} className="flex items-center justify-between">
                  <span className="capitalize">{service.replace('_', ' ')}:</span>
                  <Badge variant="outline" className="text-xs">
                    {status.replace('_', ' ')}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface DegradationWarningProps {
  mode: 'partial' | 'offline'
  serviceStatus: ServiceStatus
  onDismiss: () => void
}

function DegradationWarning({ mode, serviceStatus, onDismiss }: DegradationWarningProps) {
  const getWarningMessage = () => {
    if (mode === 'offline') {
      return {
        title: 'Limited Functionality',
        message: 'Some services are unavailable. You can still browse cached content and use offline features.',
        severity: 'critical' as const
      }
    } else {
      const issues = []
      if (serviceStatus.websocket === 'disconnected') issues.push('real-time updates')
      if (serviceStatus.ai_models === 'unavailable') issues.push('AI features')
      
      return {
        title: 'Reduced Functionality',
        message: `Some features may be limited: ${issues.join(', ')}. Core functionality remains available.`,
        severity: 'warning' as const
      }
    }
  }

  const warning = getWarningMessage()

  return (
    <div className={cn(
      'border-b',
      warning.severity === 'critical' ? 'bg-red-50/10 border-red-200' : 'bg-yellow-50/10 border-yellow-200'
    )}>
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className={cn(
              'h-5 w-5',
              warning.severity === 'critical' ? 'text-red-500' : 'text-yellow-500'
            )} />
            
            <div>
              <div className="font-medium text-foreground">
                {warning.title}
              </div>
              <div className="text-sm text-muted-foreground">
                {warning.message}
              </div>
            </div>
          </div>
          
          <Button variant="ghost" size="sm" onClick={onDismiss}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

// Hook for using graceful degradation in components
export function useGracefulDegradation() {
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({
    api: 'online',
    websocket: 'connected',
    ai_models: 'available',
    database: 'healthy'
  })

  const isFeatureAvailable = (feature: 'api' | 'websocket' | 'ai' | 'database') => {
    switch (feature) {
      case 'api':
        return serviceStatus.api === 'online'
      case 'websocket':
        return serviceStatus.websocket === 'connected'
      case 'ai':
        return serviceStatus.ai_models === 'available'
      case 'database':
        return serviceStatus.database === 'healthy'
      default:
        return false
    }
  }

  const withFallback = <T,>(
    feature: 'api' | 'websocket' | 'ai' | 'database',
    primaryAction: () => Promise<T>,
    fallbackAction: () => Promise<T> | T
  ) => {
    return async (): Promise<T> => {
      if (isFeatureAvailable(feature)) {
        try {
          return await primaryAction()
        } catch (error) {
          console.warn(`Primary action failed, using fallback:`, error)
          return await fallbackAction()
        }
      } else {
        return await fallbackAction()
      }
    }
  }

  return {
    serviceStatus,
    isFeatureAvailable,
    withFallback,
    isOnline: serviceStatus.api === 'online' && serviceStatus.database === 'healthy',
    hasRealTimeUpdates: serviceStatus.websocket === 'connected',
    hasAIFeatures: serviceStatus.ai_models === 'available'
  }
}