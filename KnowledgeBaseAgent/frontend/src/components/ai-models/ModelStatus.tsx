import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { StatusBadge } from '../ui/StatusBadge';
import { ProgressBar } from '../ui/ProgressBar';
import { cn } from '../../utils/cn';
import type { 
  ModelPhase, 
  PhaseModelConfig, 
  AvailableModels,
  ModelTestResult,
  ModelBackend
} from '../../services/aiModelService';

export interface ModelStatusProps {
  availableModels: AvailableModels;
  currentConfig: Record<ModelPhase, PhaseModelConfig | null>;
  testResults: Record<string, ModelTestResult>;
  className?: string;
}

const BACKEND_ICONS: Record<ModelBackend, string> = {
  ollama: '🦙',
  localai: '🏠',
  openai: '🤖'
};

export const ModelStatus: React.FC<ModelStatusProps> = ({
  availableModels,
  currentConfig,
  testResults,
  className
}) => {
  // Calculate overall statistics
  const stats = useMemo(() => {
    const totalPhases = Object.keys(currentConfig).length;
    const configuredPhases = Object.values(currentConfig).filter(config => config !== null).length;
    const testedPhases = Object.values(testResults).length;
    const passedTests = Object.values(testResults).filter(result => result.success).length;
    
    const configurationProgress = (configuredPhases / totalPhases) * 100;
    const testProgress = testedPhases > 0 ? (passedTests / testedPhases) * 100 : 0;
    
    return {
      totalPhases,
      configuredPhases,
      testedPhases,
      passedTests,
      configurationProgress,
      testProgress
    };
  }, [currentConfig, testResults]);

  // Calculate backend statistics
  const backendStats = useMemo(() => {
    const stats: Record<ModelBackend, {
      available: boolean;
      modelCount: number;
      configured: number;
      tested: number;
      passed: number;
    }> = {
      ollama: { available: false, modelCount: 0, configured: 0, tested: 0, passed: 0 },
      localai: { available: false, modelCount: 0, configured: 0, tested: 0, passed: 0 },
      openai: { available: false, modelCount: 0, configured: 0, tested: 0, passed: 0 }
    };

    // Count available models per backend
    Object.entries(availableModels.backends).forEach(([backend, data]) => {
      const backendKey = backend as ModelBackend;
      if (stats[backendKey]) {
        stats[backendKey].available = true;
        stats[backendKey].modelCount = data.models.length;
      }
    });

    // Count configured models per backend
    Object.values(currentConfig).forEach(config => {
      if (config && stats[config.backend]) {
        stats[config.backend].configured++;
      }
    });

    // Count test results per backend
    Object.entries(testResults).forEach(([key, result]) => {
      const [, backend] = key.split('_');
      const backendKey = backend as ModelBackend;
      if (stats[backendKey]) {
        stats[backendKey].tested++;
        if (result.success) {
          stats[backendKey].passed++;
        }
      }
    });

    return stats;
  }, [availableModels, currentConfig, testResults]);

  // Get average response time
  const averageResponseTime = useMemo(() => {
    const successfulTests = Object.values(testResults).filter(result => result.success && result.responseTime > 0);
    if (successfulTests.length === 0) return 0;
    
    const totalTime = successfulTests.reduce((sum, result) => sum + result.responseTime, 0);
    return totalTime / successfulTests.length;
  }, [testResults]);

  const formatResponseTime = (ms: number): string => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Overall Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Configuration Progress */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-2xl font-bold text-blue-600">
                {stats.configuredPhases}/{stats.totalPhases}
              </div>
              <span className="text-2xl">⚙️</span>
            </div>
            <div className="text-sm text-gray-600 mb-2">Phases Configured</div>
            <ProgressBar
              value={stats.configurationProgress}
              size="sm"
              variant={stats.configurationProgress === 100 ? 'success' : 'default'}
            />
          </CardContent>
        </Card>

        {/* Test Results */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-2xl font-bold text-green-600">
                {stats.passedTests}/{stats.testedPhases}
              </div>
              <span className="text-2xl">✅</span>
            </div>
            <div className="text-sm text-gray-600 mb-2">Tests Passed</div>
            <ProgressBar
              value={stats.testProgress}
              size="sm"
              variant={stats.testProgress === 100 ? 'success' : stats.testProgress > 0 ? 'default' : 'error'}
            />
          </CardContent>
        </Card>

        {/* Average Response Time */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-2xl font-bold text-purple-600">
                {averageResponseTime > 0 ? formatResponseTime(averageResponseTime) : 'N/A'}
              </div>
              <span className="text-2xl">⚡</span>
            </div>
            <div className="text-sm text-gray-600 mb-2">Avg Response Time</div>
            <div className="text-xs text-gray-500">
              {stats.passedTests > 0 ? `Based on ${stats.passedTests} tests` : 'No test data'}\n            </div>
          </CardContent>
        </Card>

        {/* Overall Health */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-2xl font-bold">
                <StatusBadge
                  status={
                    stats.configurationProgress === 100 && stats.testProgress === 100 ? 'completed' :
                    stats.configurationProgress > 0 ? 'running' :
                    'pending'
                  }
                  size="lg"
                />
              </div>
              <span className="text-2xl">🎯</span>
            </div>
            <div className="text-sm text-gray-600 mb-2">System Health</div>
            <div className="text-xs text-gray-500">
              {stats.configurationProgress === 100 && stats.testProgress === 100 ? 'All systems ready' :
               stats.configurationProgress > 0 ? 'Partially configured' :
               'Configuration needed'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Backend Status */}
      <Card>
        <CardHeader>
          <CardTitle>Backend Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(Object.entries(backendStats) as [ModelBackend, typeof backendStats[ModelBackend]][]).map(([backend, stats]) => (
              <div
                key={backend}
                className={cn(
                  'p-4 rounded-lg border',
                  stats.available 
                    ? 'bg-green-50 border-green-200' 
                    : 'bg-gray-50 border-gray-200'
                )}
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl">{BACKEND_ICONS[backend]}</span>
                  <div>
                    <div className="font-medium capitalize">{backend}</div>
                    <StatusBadge
                      status={stats.available ? 'completed' : 'failed'}
                      label={stats.available ? 'Available' : 'Unavailable'}
                      size="sm"
                    />
                  </div>
                </div>
                
                {stats.available && (
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Models:</span>
                      <span className="font-medium">{stats.modelCount}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Configured:</span>
                      <span className="font-medium">{stats.configured}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Tested:</span>
                      <span className="font-medium">{stats.tested}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Passed:</span>
                      <span className={cn(
                        'font-medium',
                        stats.passed === stats.tested && stats.tested > 0 ? 'text-green-600' :
                        stats.passed > 0 ? 'text-yellow-600' :
                        'text-red-600'
                      )}>
                        {stats.passed}
                      </span>
                    </div>
                  </div>
                )}
                
                {!stats.available && (
                  <div className="text-sm text-gray-500">
                    Backend not available or no models found
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Test Results */}
      {Object.keys(testResults).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Test Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(testResults)
                .slice(-5) // Show last 5 results
                .map(([key, result]) => {
                  const [phase, backend, model] = key.split('_');
                  
                  return (
                    <div
                      key={key}
                      className={cn(
                        'flex items-center justify-between p-3 rounded-lg border',
                        result.success 
                          ? 'bg-green-50 border-green-200' 
                          : 'bg-red-50 border-red-200'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg">
                          {result.success ? '✅' : '❌'}
                        </span>
                        <div>
                          <div className="font-medium text-sm">
                            {phase} / {backend} / {model}
                          </div>
                          {result.error && (
                            <div className="text-xs text-red-600 mt-1">
                              {result.error}
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {result.success && result.responseTime > 0 && (
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {formatResponseTime(result.responseTime)}
                          </div>
                          <div className="text-xs text-gray-500">
                            Response time
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};