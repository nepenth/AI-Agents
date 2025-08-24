import React from 'react';
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';
import { cn } from '@/utils/cn';

interface ErrorInfo {
  componentStack: string;
  errorBoundary?: string;
  errorBoundaryStack?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<ErrorFallbackProps>;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  isolate?: boolean; // Whether to isolate this boundary from parent boundaries
  level?: 'page' | 'component' | 'feature'; // Error boundary level for different handling
}

interface ErrorFallbackProps {
  error: Error;
  errorInfo: ErrorInfo;
  resetError: () => void;
  errorId: string;
  level: string;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private resetTimeoutId: number | null = null;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    const errorId = `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    return {
      hasError: true,
      error,
      errorId
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { onError, level = 'component' } = this.props;
    
    this.setState({
      errorInfo
    });

    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.group(`🚨 Error Boundary (${level})`);
      console.error('Error:', error);
      console.error('Error Info:', errorInfo);
      console.error('Component Stack:', errorInfo.componentStack);
      console.groupEnd();
    }

    // Send error to monitoring service
    this.reportError(error, errorInfo);

    // Call custom error handler
    if (onError) {
      onError(error, errorInfo);
    }
  }

  private reportError = async (error: Error, errorInfo: ErrorInfo) => {
    try {
      const errorReport = {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        errorId: this.state.errorId,
        level: this.props.level || 'component',
        userId: this.getUserId(), // Implement based on your auth system
        sessionId: this.getSessionId() // Implement based on your session management
      };

      // Send to error reporting service
      await fetch('/api/v1/errors/report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(errorReport)
      });
    } catch (reportingError) {
      console.error('Failed to report error:', reportingError);
    }
  };

  private getUserId = (): string | null => {
    // Implement based on your authentication system
    try {
      const user = localStorage.getItem('user');
      return user ? JSON.parse(user).id : null;
    } catch {
      return null;
    }
  };

  private getSessionId = (): string | null => {
    // Implement based on your session management
    try {
      return sessionStorage.getItem('sessionId');
    } catch {
      return null;
    }
  };

  private resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null
    });
  };

  private handleRetry = () => {
    this.resetError();
    
    // Auto-retry after a delay to prevent infinite loops
    if (this.resetTimeoutId) {
      clearTimeout(this.resetTimeoutId);
    }
    
    this.resetTimeoutId = window.setTimeout(() => {
      if (this.state.hasError) {
        console.warn('Error boundary auto-retry failed, manual intervention required');
      }
    }, 5000);
  };

  componentWillUnmount() {
    if (this.resetTimeoutId) {
      clearTimeout(this.resetTimeoutId);
    }
  }

  render() {
    const { hasError, error, errorInfo, errorId } = this.state;
    const { children, fallback: CustomFallback, level = 'component' } = this.props;

    if (hasError && error && errorInfo && errorId) {
      if (CustomFallback) {
        return (
          <CustomFallback
            error={error}
            errorInfo={errorInfo}
            resetError={this.resetError}
            errorId={errorId}
            level={level}
          />
        );
      }

      return (
        <DefaultErrorFallback
          error={error}
          errorInfo={errorInfo}
          resetError={this.handleRetry}
          errorId={errorId}
          level={level}
        />
      );
    }

    return children;
  }
}

// Default error fallback component
function DefaultErrorFallback({ 
  error, 
  errorInfo, 
  resetError, 
  errorId, 
  level 
}: ErrorFallbackProps) {
  const [showDetails, setShowDetails] = React.useState(false);
  const [reportSent, setReportSent] = React.useState(false);

  const handleSendReport = async () => {
    try {
      const userReport = {
        errorId,
        userDescription: 'User-reported error',
        reproductionSteps: 'Not provided',
        expectedBehavior: 'Not provided',
        actualBehavior: error.message
      };

      await fetch('/api/v1/errors/user-report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(userReport)
      });

      setReportSent(true);
    } catch (reportError) {
      console.error('Failed to send user report:', reportError);
    }
  };

  const getErrorSeverity = () => {
    switch (level) {
      case 'page':
        return {
          title: 'Page Error',
          description: 'This page encountered an error and cannot be displayed.',
          severity: 'high'
        };
      case 'feature':
        return {
          title: 'Feature Error',
          description: 'A feature on this page is not working correctly.',
          severity: 'medium'
        };
      default:
        return {
          title: 'Component Error',
          description: 'A component on this page encountered an error.',
          severity: 'low'
        };
    }
  };

  const { title, description, severity } = getErrorSeverity();

  return (
    <div className={cn(
      'flex items-center justify-center p-6',
      level === 'page' ? 'min-h-screen' : 'min-h-[200px]'
    )}>
      <GlassCard className={cn(
        'max-w-lg w-full p-6 text-center',
        severity === 'high' && 'border-red-500/30 bg-red-500/5',
        severity === 'medium' && 'border-yellow-500/30 bg-yellow-500/5',
        severity === 'low' && 'border-blue-500/30 bg-blue-500/5'
      )}>
        <div className="flex flex-col items-center gap-4">
          <div className={cn(
            'p-3 rounded-full',
            severity === 'high' && 'bg-red-500/20 text-red-500',
            severity === 'medium' && 'bg-yellow-500/20 text-yellow-500',
            severity === 'low' && 'bg-blue-500/20 text-blue-500'
          )}>
            <AlertTriangle className="h-8 w-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold text-foreground">{title}</h2>
            <p className="text-muted-foreground">{description}</p>
          </div>

          <div className="text-sm text-muted-foreground">
            <p>Error ID: <code className="bg-muted px-1 rounded">{errorId}</code></p>
            <p className="mt-1">
              {error.message && (
                <span className="font-mono text-xs bg-muted px-2 py-1 rounded">
                  {error.message}
                </span>
              )}
            </p>
          </div>

          <div className="flex flex-wrap gap-2 justify-center">
            <Button onClick={resetError} className="flex items-center gap-2">
              <RefreshCw className="h-4 w-4" />
              Try Again
            </Button>

            {level === 'page' && (
              <Button 
                variant="outline" 
                onClick={() => window.location.href = '/'}
                className="flex items-center gap-2"
              >
                <Home className="h-4 w-4" />
                Go Home
              </Button>
            )}

            <Button
              variant="outline"
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-2"
            >
              <Bug className="h-4 w-4" />
              {showDetails ? 'Hide' : 'Show'} Details
            </Button>
          </div>

          {showDetails && (
            <div className="w-full mt-4 space-y-4">
              <div className="text-left">
                <h3 className="font-semibold mb-2">Error Details</h3>
                <div className="bg-muted p-3 rounded text-xs font-mono overflow-auto max-h-32">
                  <div className="mb-2">
                    <strong>Message:</strong> {error.message}
                  </div>
                  {error.stack && (
                    <div className="mb-2">
                      <strong>Stack:</strong>
                      <pre className="mt-1 whitespace-pre-wrap">{error.stack}</pre>
                    </div>
                  )}
                </div>
              </div>

              <div className="text-left">
                <h3 className="font-semibold mb-2">Component Stack</h3>
                <div className="bg-muted p-3 rounded text-xs font-mono overflow-auto max-h-32">
                  <pre className="whitespace-pre-wrap">{errorInfo.componentStack}</pre>
                </div>
              </div>

              <div className="flex justify-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSendReport}
                  disabled={reportSent}
                  className="flex items-center gap-2"
                >
                  {reportSent ? 'Report Sent' : 'Send Error Report'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </GlassCard>
    </div>
  );
}

// Higher-order component for easy wrapping
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;
  
  return WrappedComponent;
}

// Hook for programmatically triggering error boundaries
export function useErrorHandler() {
  return React.useCallback((error: Error, errorInfo?: Partial<ErrorInfo>) => {
    // This will trigger the nearest error boundary
    throw error;
  }, []);
}

// Custom hook for error reporting
export function useErrorReporting() {
  const reportError = React.useCallback(async (
    error: Error,
    context?: Record<string, any>
  ) => {
    try {
      const errorReport = {
        message: error.message,
        stack: error.stack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        context: context || {},
        type: 'manual'
      };

      await fetch('/api/v1/errors/report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(errorReport)
      });
    } catch (reportingError) {
      console.error('Failed to report error:', reportingError);
    }
  }, []);

  return { reportError };
}