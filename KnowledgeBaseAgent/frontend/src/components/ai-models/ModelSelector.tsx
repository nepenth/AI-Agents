import React, { useState, useCallback, useMemo } from 'react';
import { Button } from '../ui/Button';
import { StatusBadge } from '../ui/StatusBadge';
import { cn } from '../../utils/cn';
import type { 
  ModelPhase, 
  PhaseModelConfig, 
  ModelBackend, 
  AvailableModels 
} from '../../services/aiModelService';

export interface ModelSelectorProps {
  phase: ModelPhase;
  availableModels: AvailableModels | null;
  currentConfig: PhaseModelConfig | null;
  onConfigChange: (config: PhaseModelConfig | null) => void;
  className?: string;
}

const BACKEND_INFO: Record<ModelBackend, { name: string; icon: string; description: string }> = {
  ollama: {
    name: 'Ollama',
    icon: '🦙',
    description: 'Local AI models with privacy and control'
  },
  localai: {
    name: 'LocalAI',
    icon: '🏠',
    description: 'OpenAI-compatible local inference'
  },
  openai: {
    name: 'OpenAI',
    icon: '🤖',
    description: 'OpenAI API and compatible services'
  }
};

const PHASE_CAPABILITIES: Record<ModelPhase, string[]> = {
  vision: ['vision', 'multimodal'],
  kb_generation: ['text', 'instruct'],
  synthesis: ['text', 'instruct'],
  chat: ['text', 'instruct', 'chat'],
  embeddings: ['embed', 'embeddings']
};

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  phase,
  availableModels,
  currentConfig,
  onConfigChange,
  className
}) => {
  const [selectedBackend, setSelectedBackend] = useState<ModelBackend | null>(
    currentConfig?.backend || null
  );
  const [selectedModel, setSelectedModel] = useState<string | null>(
    currentConfig?.model || null
  );
  const [customParams, setCustomParams] = useState<Record<string, any>>(
    currentConfig?.params || {}
  );
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Get available backends
  const availableBackends = useMemo(() => {
    if (!availableModels) return [];
    return Object.keys(availableModels.backends) as ModelBackend[];
  }, [availableModels]);

  // Get available models for selected backend
  const availableModelsForBackend = useMemo(() => {
    if (!availableModels || !selectedBackend) return [];
    
    const backend = availableModels.backends[selectedBackend];
    if (!backend) return [];
    
    const requiredCapabilities = PHASE_CAPABILITIES[phase];
    
    return backend.models.filter(model => {
      const modelCapabilities = backend.capabilities[model] || [];
      return requiredCapabilities.some(cap => 
        modelCapabilities.some(modelCap => 
          modelCap.toLowerCase().includes(cap.toLowerCase()) ||
          cap.toLowerCase().includes(modelCap.toLowerCase())
        )
      );
    });
  }, [availableModels, selectedBackend, phase]);

  // Check if a model has required capabilities
  const hasRequiredCapabilities = useCallback((backend: ModelBackend, model: string): boolean => {
    if (!availableModels) return false;
    
    const backendData = availableModels.backends[backend];
    if (!backendData) return false;
    
    const modelCapabilities = backendData.capabilities[model] || [];
    const requiredCapabilities = PHASE_CAPABILITIES[phase];
    
    return requiredCapabilities.some(cap => 
      modelCapabilities.some(modelCap => 
        modelCap.toLowerCase().includes(cap.toLowerCase()) ||
        cap.toLowerCase().includes(modelCap.toLowerCase())
      )
    );
  }, [availableModels, phase]);

  // Handle backend selection
  const handleBackendChange = useCallback((backend: ModelBackend) => {
    setSelectedBackend(backend);
    setSelectedModel(null);
    
    // Clear configuration when backend changes
    onConfigChange(null);
  }, [onConfigChange]);

  // Handle model selection
  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
    
    if (selectedBackend) {
      const config: PhaseModelConfig = {
        backend: selectedBackend,
        model,
        params: customParams
      };
      onConfigChange(config);
    }
  }, [selectedBackend, customParams, onConfigChange]);

  // Handle parameter changes
  const handleParamChange = useCallback((key: string, value: any) => {
    const newParams = { ...customParams, [key]: value };
    setCustomParams(newParams);
    
    if (selectedBackend && selectedModel) {
      const config: PhaseModelConfig = {
        backend: selectedBackend,
        model: selectedModel,
        params: newParams
      };
      onConfigChange(config);
    }
  }, [selectedBackend, selectedModel, customParams, onConfigChange]);

  // Clear configuration
  const clearConfiguration = useCallback(() => {
    setSelectedBackend(null);
    setSelectedModel(null);
    setCustomParams({});
    onConfigChange(null);
  }, [onConfigChange]);

  if (!availableModels) {
    return (
      <div className={cn('p-4 bg-gray-50 rounded-lg', className)}>
        <div className="text-sm text-gray-500">Loading available models...</div>
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Backend Selection */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          AI Backend
        </label>
        <div className="grid grid-cols-1 gap-2">
          {availableBackends.map((backend) => {
            const info = BACKEND_INFO[backend];
            const backendData = availableModels.backends[backend];
            const isSelected = selectedBackend === backend;
            const isAvailable = backendData && backendData.models.length > 0;
            
            return (
              <button
                key={backend}
                onClick={() => isAvailable ? handleBackendChange(backend) : undefined}
                disabled={!isAvailable}
                className={cn(
                  'p-3 border rounded-lg text-left transition-all duration-200',
                  {
                    'border-blue-300 bg-blue-50 ring-2 ring-blue-200': isSelected,
                    'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50': !isSelected && isAvailable,
                    'border-gray-100 bg-gray-50 text-gray-400 cursor-not-allowed': !isAvailable
                  }
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{info.icon}</span>
                    <div>
                      <div className="font-medium">{info.name}</div>
                      <div className="text-sm text-gray-600">{info.description}</div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {isAvailable ? (
                      <StatusBadge status="completed" label={`${backendData.models.length} models`} size="sm" />
                    ) : (
                      <StatusBadge status="failed" label="Unavailable" size="sm" />
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Model Selection */}
      {selectedBackend && availableModelsForBackend.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Model ({availableModelsForBackend.length} compatible)
          </label>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {availableModelsForBackend.map((model) => {
              const isSelected = selectedModel === model;
              const hasCapabilities = hasRequiredCapabilities(selectedBackend, model);
              const capabilities = availableModels.backends[selectedBackend]?.capabilities[model] || [];
              
              return (
                <button
                  key={model}
                  onClick={() => handleModelChange(model)}
                  className={cn(
                    'w-full p-3 border rounded-lg text-left transition-all duration-200',
                    {
                      'border-blue-300 bg-blue-50 ring-2 ring-blue-200': isSelected,
                      'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50': !isSelected
                    }
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="font-medium">{model}</div>
                      <div className="flex items-center gap-2 mt-1">
                        {capabilities.map((cap) => (
                          <span
                            key={cap}
                            className={cn(
                              'text-xs px-2 py-1 rounded-full',
                              PHASE_CAPABILITIES[phase].some(required => 
                                cap.toLowerCase().includes(required.toLowerCase()) ||
                                required.toLowerCase().includes(cap.toLowerCase())
                              )
                                ? 'bg-green-100 text-green-800'
                                : 'bg-gray-100 text-gray-600'
                            )}
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    </div>
                    
                    {hasCapabilities && (
                      <StatusBadge status="completed" size="sm" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* No Compatible Models */}
      {selectedBackend && availableModelsForBackend.length === 0 && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center gap-2">
            <span className="text-yellow-600">⚠️</span>
            <div>
              <div className="font-medium text-yellow-800">No Compatible Models</div>
              <div className="text-yellow-700 text-sm mt-1">
                No models found for {BACKEND_INFO[selectedBackend].name} that support the required capabilities for {phase} phase.
              </div>
              <div className="text-yellow-600 text-xs mt-2">
                Required: {PHASE_CAPABILITIES[phase].join(', ')}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Advanced Parameters */}
      {selectedBackend && selectedModel && (
        <div>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800"
          >
            <span className={cn('transition-transform', { 'rotate-90': showAdvanced })}>▶</span>
            Advanced Parameters
          </button>
          
          {showAdvanced && (
            <div className="mt-3 p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Temperature
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    value={customParams.temperature || 0.7}
                    onChange={(e) => handleParamChange('temperature', parseFloat(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Tokens
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="4096"
                    value={customParams.max_tokens || 1000}
                    onChange={(e) => handleParamChange('max_tokens', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Top P
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={customParams.top_p || 0.9}
                    onChange={(e) => handleParamChange('top_p', parseFloat(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Top K
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={customParams.top_k || 40}
                    onChange={(e) => handleParamChange('top_k', parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      {currentConfig && (
        <div className="flex justify-end">
          <Button
            onClick={clearConfiguration}
            variant="outline"
            size="sm"
          >
            Clear Configuration
          </Button>
        </div>
      )}
    </div>
  );
};