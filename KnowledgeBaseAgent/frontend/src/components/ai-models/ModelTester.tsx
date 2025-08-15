import React, { useState, useCallback } from 'react';
import { Button } from '../ui/Button';
import { StatusBadge } from '../ui/StatusBadge';
import { ProgressBar } from '../ui/ProgressBar';
import { aiModelService } from '../../services/aiModelService';
import { cn } from '../../utils/cn';
import type { 
  ModelPhase, 
  PhaseModelConfig, 
  ModelTestResult 
} from '../../services/aiModelService';

export interface ModelTesterProps {
  phase: ModelPhase;
  config: PhaseModelConfig;
  testResult?: ModelTestResult | null;
  onTestComplete?: (result: ModelTestResult) => void;
  className?: string;
}

const TEST_PROMPTS: Record<ModelPhase, { prompt: string; expectedType: string }> = {
  vision: {
    prompt: 'Describe what you see in this image: [test image]',
    expectedType: 'image analysis'
  },
  kb_generation: {
    prompt: 'Generate a brief summary of this content: "AI and machine learning are transforming how we process information."',
    expectedType: 'text generation'
  },
  synthesis: {
    prompt: 'Create a synthesis of these topics: artificial intelligence, automation, future of work.',
    expectedType: 'synthesis generation'
  },
  chat: {
    prompt: 'Hello! How can you help me with AI-related questions?',
    expectedType: 'conversational response'
  },
  embeddings: {
    prompt: 'Generate embeddings for: "machine learning algorithms"',
    expectedType: 'vector embeddings'
  }
};

const formatResponseTime = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
};

const getPerformanceRating = (responseTime: number): { rating: string; color: string } => {
  if (responseTime < 1000) return { rating: 'Excellent', color: 'text-green-600' };
  if (responseTime < 3000) return { rating: 'Good', color: 'text-blue-600' };
  if (responseTime < 10000) return { rating: 'Fair', color: 'text-yellow-600' };
  return { rating: 'Slow', color: 'text-red-600' };
};

export const ModelTester: React.FC<ModelTesterProps> = ({
  phase,
  config,
  testResult,
  onTestComplete,
  className
}) => {
  const [isTesting, setIsTesting] = useState(false);
  const [testProgress, setTestProgress] = useState(0);
  const [customPrompt, setCustomPrompt] = useState('');
  const [showCustomPrompt, setShowCustomPrompt] = useState(false);

  const runTest = useCallback(async (prompt?: string) => {
    setIsTesting(true);
    setTestProgress(0);
    
    // Simulate progress updates
    const progressInterval = setInterval(() => {
      setTestProgress(prev => Math.min(prev + 10, 90));
    }, 200);
    
    try {
      const result = await aiModelService.testModel(
        config.backend,
        config.model,
        phase,
        prompt || TEST_PROMPTS[phase].prompt
      );
      
      setTestProgress(100);
      onTestComplete?.(result);
    } catch (error) {
      const errorResult: ModelTestResult = {
        success: false,
        error: error instanceof Error ? error.message : 'Test failed',
        responseTime: 0,
        capabilities: []
      };
      onTestComplete?.(errorResult);
    } finally {
      clearInterval(progressInterval);
      setIsTesting(false);
      setTestProgress(0);
    }
  }, [config, phase, onTestComplete]);

  const runQuickTest = useCallback(() => {
    runTest();
  }, [runTest]);

  const runCustomTest = useCallback(() => {
    if (customPrompt.trim()) {
      runTest(customPrompt.trim());
    }
  }, [customPrompt, runTest]);

  const performance = testResult?.responseTime ? getPerformanceRating(testResult.responseTime) : null;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Test Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            onClick={runQuickTest}
            disabled={isTesting}
            loading={isTesting}
            size="sm"
          >
            {isTesting ? 'Testing...' : 'Quick Test'}
          </Button>
          
          <button
            onClick={() => setShowCustomPrompt(!showCustomPrompt)}
            className="text-sm text-gray-600 hover:text-gray-800"
          >
            Custom Test
          </button>
        </div>
        
        {testResult && (
          <StatusBadge
            status={testResult.success ? 'completed' : 'failed'}
            label={testResult.success ? 'Passed' : 'Failed'}
            size="sm"
          />
        )}
      </div>

      {/* Progress Bar */}
      {isTesting && (
        <ProgressBar
          value={testProgress}
          variant="default"
          size="sm"
          animated
          striped
          showLabel
          label="Testing model..."
        />
      )}

      {/* Custom Prompt */}
      {showCustomPrompt && (
        <div className="space-y-2">
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder={`Enter custom prompt for ${phase} testing...`}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            rows={3}
          />
          <div className="flex justify-end">
            <Button
              onClick={runCustomTest}
              disabled={!customPrompt.trim() || isTesting}
              size="sm"
            >
              Run Custom Test
            </Button>
          </div>
        </div>
      )}

      {/* Test Results */}
      {testResult && (
        <div className={cn(
          'p-4 rounded-lg border',
          testResult.success 
            ? 'bg-green-50 border-green-200' 
            : 'bg-red-50 border-red-200'
        )}>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">
                {testResult.success ? '✅' : '❌'}
              </span>
              <div>
                <div className={cn(
                  'font-medium',
                  testResult.success ? 'text-green-800' : 'text-red-800'
                )}>
                  {testResult.success ? 'Test Passed' : 'Test Failed'}
                </div>
                <div className={cn(
                  'text-sm',
                  testResult.success ? 'text-green-700' : 'text-red-700'
                )}>
                  {config.backend} / {config.model}
                </div>
              </div>
            </div>
            
            {testResult.success && testResult.responseTime > 0 && (
              <div className="text-right">
                <div className={cn('font-medium', performance?.color)}>
                  {formatResponseTime(testResult.responseTime)}
                </div>
                <div className={cn('text-xs', performance?.color)}>
                  {performance?.rating}
                </div>
              </div>
            )}
          </div>

          {/* Error Message */}
          {!testResult.success && testResult.error && (
            <div className="mb-3">
              <div className="text-sm font-medium text-red-800 mb-1">Error Details:</div>
              <div className="text-sm text-red-700 bg-red-100 p-2 rounded">
                {testResult.error}
              </div>
            </div>
          )}

          {/* Capabilities */}
          {testResult.capabilities && testResult.capabilities.length > 0 && (
            <div className="mb-3">
              <div className="text-sm font-medium text-gray-700 mb-2">Detected Capabilities:</div>
              <div className="flex flex-wrap gap-2">
                {testResult.capabilities.map((capability) => (
                  <span
                    key={capability}
                    className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded-full"
                  >
                    {capability}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Response Sample */}
          {testResult.success && testResult.response && (
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">Sample Response:</div>
              <div className="text-sm text-gray-600 bg-gray-100 p-3 rounded max-h-32 overflow-y-auto">
                {typeof testResult.response === 'string' 
                  ? testResult.response.length > 200 
                    ? `${testResult.response.substring(0, 200)}...`
                    : testResult.response
                  : JSON.stringify(testResult.response, null, 2)
                }
              </div>
            </div>
          )}

          {/* Performance Metrics */}
          {testResult.success && testResult.responseTime > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="font-medium text-gray-700">Response Time</div>
                  <div className="text-gray-600">{formatResponseTime(testResult.responseTime)}</div>
                </div>
                <div>
                  <div className="font-medium text-gray-700">Performance</div>
                  <div className={performance?.color}>{performance?.rating}</div>
                </div>
                <div>
                  <div className="font-medium text-gray-700">Expected</div>
                  <div className="text-gray-600">{TEST_PROMPTS[phase].expectedType}</div>
                </div>
                <div>
                  <div className="font-medium text-gray-700">Status</div>
                  <div className="text-green-600">✓ Compatible</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Test Information */}
      {!testResult && !isTesting && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-2">
            <span className="text-blue-600">ℹ️</span>
            <div className="text-sm">
              <div className="font-medium text-blue-800 mb-1">Test Information</div>
              <div className="text-blue-700">
                This will test the model's ability to handle {TEST_PROMPTS[phase].expectedType} tasks.
                The test will verify connectivity, response time, and capability compatibility.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};