import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { StatusBadge } from '../ui/StatusBadge';
import { ModelSelector } from './ModelSelector';
import { ModelTester } from './ModelTester';
import { ModelStatus } from './ModelStatus';
import { aiModelService } from '../../services/aiModelService';
import { cn } from '../../utils/cn';
import type { 
  ModelPhase, 
  PhaseModelConfig, 
  ModelBackend, 
  AvailableModels,
  ModelTestResult 
} from '../../services/aiModelService';

export interface ModelConfigurationProps {
  className?: string;
  onConfigurationChange?: (config: Record<ModelPhase, PhaseModelConfig | null>) => void;
  onTestComplete?: (results: Record<string, ModelTestResult>) => void;
}

const PHASE_DESCRIPTIONS: Record<ModelPhase, { name: string; description: string; icon: string }> = {
  vision: {
    name: 'Vision Analysis',
    description: 'Analyze images and media content from tweets',
    icon: '👁️'
  },
  kb_generation: {
    name: 'Knowledge Generation',
    description: 'Generate content understanding and categorization',
    icon: '🧠'
  },
  synthesis: {
    name: 'Synthesis Generation',
    description: 'Create synthesis documents from related content',
    icon: '📝'
  },
  chat: {
    name: 'Chat Interface',
    description: 'Handle conversational AI interactions',
    icon: '💬'
  },
  embeddings: {
    name: 'Embeddings Generation',
    description: 'Generate vector embeddings for semantic search',
    icon: '🔢'
  }
};

export const ModelConfiguration: React.FC<ModelConfigurationProps> = ({
  className,
  onConfigurationChange,
  onTestComplete
}) => {
  const [availableModels, setAvailableModels] = useState<AvailableModels | null>(null);
  const [currentConfig, setCurrentConfig] = useState<Record<ModelPhase, PhaseModelConfig | null>>({
    vision: null,
    kb_generation: null,
    synthesis: null,
    chat: null,
    embeddings: null
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ModelTestResult>>({});
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Load available models and current configuration
  const loadConfiguration = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const [models, config] = await Promise.all([
        aiModelService.getAvailableModels(),
        aiModelService.getCurrentConfiguration()
      ]);
      
      setAvailableModels(models);
      setCurrentConfig(config.perPhase);
      setHasUnsavedChanges(false);
    } catch (err) {
      console.error('Failed to load model configuration:', err);
      setError(
        err instanceof Error 
          ? err.message 
          : 'Failed to load model configuration'
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load configuration on mount
  useEffect(() => {
    loadConfiguration();
  }, [loadConfiguration]);

  // Handle phase configuration change
  const handlePhaseConfigChange = useCallback((
    phase: ModelPhase, 
    config: PhaseModelConfig | null
  ) => {
    setCurrentConfig(prev => {
      const newConfig = { ...prev, [phase]: config };
      setHasUnsavedChanges(true);
      onConfigurationChange?.(newConfig);
      return newConfig;
    });
  }, [onConfigurationChange]);

  // Save configuration
  const saveConfiguration = useCallback(async () => {
    setIsSaving(true);
    setError(null);
    
    try {
      await aiModelService.updateConfiguration({ perPhase: currentConfig });
      setHasUnsavedChanges(false);
    } catch (err) {
      console.error('Failed to save configuration:', err);
      setError(
        err instanceof Error 
          ? err.message 
          : 'Failed to save configuration'
      );
    } finally {
      setIsSaving(false);
    }
  }, [currentConfig]);

  // Reset configuration
  const resetConfiguration = useCallback(() => {
    loadConfiguration();
  }, [loadConfiguration]);

  // Test all configured models
  const testAllModels = useCallback(async () => {
    if (!availableModels) return;
    
    const results: Record<string, ModelTestResult> = {};
    
    for (const [phase, config] of Object.entries(currentConfig)) {
      if (config) {
        try {
          const result = await aiModelService.testModel(
            config.backend,
            config.model,
            phase as ModelPhase
          );
          results[`${phase}_${config.backend}_${config.model}`] = result;
        } catch (err) {
          results[`${phase}_${config.backend}_${config.model}`] = {
            success: false,
            error: err instanceof Error ? err.message : 'Test failed',
            responseTime: 0,
            capabilities: []
          };
        }
      }
    }
    
    setTestResults(results);
    onTestComplete?.(results);
  }, [currentConfig, availableModels, onTestComplete]);

  // Get test result for a specific phase configuration
  const getTestResult = useCallback((phase: ModelPhase): ModelTestResult | null => {
    const config = currentConfig[phase];
    if (!config) return null;
    
    const key = `${phase}_${config.backend}_${config.model}`;
    return testResults[key] || null;
  }, [currentConfig, testResults]);

  if (isLoading) {
    return (
      <Card className={cn('p-8', className)}>
        <div className="flex items-center justify-center">
          <LoadingSpinner size="lg" />
          <span className="ml-3 text-gray-600">Loading model configuration...</span>
        </div>
      </Card>
    );
  }

  if (error && !availableModels) {
    return (
      <Card className={cn('border-red-200 bg-red-50', className)}>
        <CardContent className="p-6">
          <div className="flex items-center gap-3">
            <span className="text-red-600 text-xl">❌</span>
            <div>
              <div className="font-medium text-red-800">Configuration Error</div>
              <div className="text-red-700 text-sm mt-1">{error}</div>
            </div>
          </div>
          <Button 
            onClick={loadConfiguration} 
            variant="outline" 
            className="mt-4"
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">AI Model Configuration</h2>
          <p className="text-gray-600 mt-1">
            Configure AI models for each phase of the processing pipeline
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {hasUnsavedChanges && (
            <StatusBadge status="warning" label="Unsaved Changes" />
          )}
          
          <Button
            onClick={testAllModels}
            variant="outline"
            disabled={!Object.values(currentConfig).some(config => config !== null)}
          >
            Test All Models
          </Button>
          
          <Button
            onClick={resetConfiguration}
            variant="outline"
            disabled={!hasUnsavedChanges}
          >
            Reset
          </Button>
          
          <Button
            onClick={saveConfiguration}
            loading={isSaving}
            disabled={!hasUnsavedChanges}
          >
            Save Configuration
          </Button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <span className="text-red-600">❌</span>
              <span className="text-red-800 text-sm font-medium">Error:</span>
            </div>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Model Status Overview */}
      {availableModels && (
        <ModelStatus 
          availableModels={availableModels}
          currentConfig={currentConfig}
          testResults={testResults}
        />
      )}

      {/* Phase Configuration Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {(Object.entries(PHASE_DESCRIPTIONS) as [ModelPhase, typeof PHASE_DESCRIPTIONS[ModelPhase]][]).map(([phase, info]) => {
          const config = currentConfig[phase];
          const testResult = getTestResult(phase);
          
          return (
            <Card key={phase} className="border-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <span className="text-2xl">{info.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      {info.name}
                      {config && (
                        <StatusBadge 
                          status={testResult?.success ? 'completed' : testResult?.success === false ? 'failed' : 'pending'}
                          size="sm"
                        />
                      )}
                    </div>
                    <p className="text-sm text-gray-600 font-normal mt-1">
                      {info.description}
                    </p>
                  </div>
                </CardTitle>
              </CardHeader>
              
              <CardContent className="space-y-4">
                {/* Model Selector */}
                <ModelSelector
                  phase={phase}
                  availableModels={availableModels}
                  currentConfig={config}
                  onConfigChange={(newConfig) => handlePhaseConfigChange(phase, newConfig)}
                />
                
                {/* Model Tester */}
                {config && (
                  <ModelTester
                    phase={phase}
                    config={config}
                    testResult={testResult}
                    onTestComplete={(result) => {
                      const key = `${phase}_${config.backend}_${config.model}`;
                      setTestResults(prev => ({ ...prev, [key]: result }));
                    }}
                  />
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Configuration Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(Object.entries(PHASE_DESCRIPTIONS) as [ModelPhase, typeof PHASE_DESCRIPTIONS[ModelPhase]][]).map(([phase, info]) => {
              const config = currentConfig[phase];
              const testResult = getTestResult(phase);
              
              return (
                <div key={phase} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <span>{info.icon}</span>
                    <span className="font-medium text-sm">{info.name}</span>
                    {testResult && (
                      <StatusBadge 
                        status={testResult.success ? 'completed' : 'failed'}
                        size="sm"
                      />
                    )}
                  </div>
                  
                  {config ? (
                    <div className="text-xs text-gray-600">
                      <div className="font-medium">{config.backend}</div>
                      <div>{config.model}</div>
                      {testResult?.responseTime && (
                        <div className="text-green-600 mt-1">
                          {testResult.responseTime}ms response
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-gray-500">Not configured</div>
                  )}
                </div>
              );
            })}
          </div>
          
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">
                {Object.values(currentConfig).filter(config => config !== null).length} of {Object.keys(currentConfig).length} phases configured
              </span>
              
              {Object.values(testResults).length > 0 && (
                <span className="text-gray-600">
                  {Object.values(testResults).filter(result => result.success).length} of {Object.values(testResults).length} tests passed
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};