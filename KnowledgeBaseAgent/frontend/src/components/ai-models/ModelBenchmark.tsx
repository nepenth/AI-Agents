import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
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

export interface BenchmarkTest {
  id: string;
  name: string;
  description: string;
  prompt: string;
  iterations: number;
  timeout: number;
}

export interface BenchmarkResult {
  testId: string;
  iterations: number;
  successCount: number;
  failureCount: number;
  averageResponseTime: number;
  minResponseTime: number;
  maxResponseTime: number;
  throughput: number; // requests per second
  errorRate: number; // percentage
  responses: Array<{
    success: boolean;
    responseTime: number;
    error?: string;
  }>;
}

export interface ModelBenchmarkProps {
  phase: ModelPhase;
  config: PhaseModelConfig;
  onBenchmarkComplete?: (results: BenchmarkResult[]) => void;
  className?: string;
}

const BENCHMARK_TESTS: Record<ModelPhase, BenchmarkTest[]> = {
  vision: [
    {
      id: 'vision_speed',
      name: 'Image Analysis Speed',
      description: 'Test response time for image analysis tasks',
      prompt: 'Describe this image briefly in one sentence.',
      iterations: 5,
      timeout: 30000
    },
    {
      id: 'vision_load',
      name: 'Vision Load Test',
      description: 'Test performance under concurrent image analysis requests',
      prompt: 'Analyze this image and identify the main objects.',
      iterations: 10,
      timeout: 45000
    }
  ],
  kb_generation: [
    {
      id: 'kb_speed',
      name: 'Content Generation Speed',
      description: 'Test response time for content understanding tasks',
      prompt: 'Summarize this content: "AI is transforming industries worldwide."',
      iterations: 10,
      timeout: 20000
    },
    {
      id: 'kb_consistency',
      name: 'Generation Consistency',
      description: 'Test consistency of content generation across multiple runs',
      prompt: 'Generate 3 key insights from this tweet: "Just launched our new AI product!"',
      iterations: 15,
      timeout: 25000
    }
  ],
  synthesis: [
    {
      id: 'synthesis_speed',
      name: 'Synthesis Speed',
      description: 'Test response time for synthesis generation',
      prompt: 'Create a synthesis connecting AI ethics and automation.',
      iterations: 8,
      timeout: 30000
    }
  ],
  chat: [
    {
      id: 'chat_speed',
      name: 'Chat Response Speed',
      description: 'Test response time for conversational interactions',
      prompt: 'Hello! How can you help me today?',
      iterations: 20,
      timeout: 15000
    },
    {
      id: 'chat_load',
      name: 'Chat Load Test',
      description: 'Test performance under high chat volume',
      prompt: 'Explain machine learning in simple terms.',
      iterations: 25,
      timeout: 20000
    }
  ],
  embeddings: [
    {
      id: 'embeddings_speed',
      name: 'Embedding Generation Speed',
      description: 'Test response time for vector embedding generation',
      prompt: 'machine learning and artificial intelligence',
      iterations: 30,
      timeout: 10000
    },
    {
      id: 'embeddings_batch',
      name: 'Batch Embedding Test',
      description: 'Test performance for batch embedding generation',
      prompt: 'AI technology innovation',
      iterations: 50,
      timeout: 15000
    }
  ]
};

export const ModelBenchmark: React.FC<ModelBenchmarkProps> = ({
  phase,
  config,
  onBenchmarkComplete,
  className
}) => {
  const [isRunning, setBenchmarkRunning] = useState(false);
  const [currentTest, setCurrentTest] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const [selectedTests, setSelectedTests] = useState<string[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  const availableTests = BENCHMARK_TESTS[phase] || [];

  // Initialize selected tests
  useEffect(() => {
    if (selectedTests.length === 0 && availableTests.length > 0) {
      setSelectedTests([availableTests[0].id]); // Select first test by default
    }
  }, [availableTests, selectedTests.length]);

  // Run a single benchmark test
  const runBenchmarkTest = useCallback(async (
    test: BenchmarkTest,
    signal: AbortSignal
  ): Promise<BenchmarkResult> => {
    const responses: BenchmarkResult['responses'] = [];
    let completedIterations = 0;

    setCurrentTest(test.name);

    for (let i = 0; i < test.iterations; i++) {
      if (signal.aborted) break;

      try {
        const startTime = Date.now();
        const result = await aiModelService.testModel(
          config.backend,
          config.model,
          phase,
          test.prompt
        );
        const responseTime = Date.now() - startTime;

        responses.push({
          success: result.success,
          responseTime,
          error: result.error
        });

        completedIterations++;
        setProgress((completedIterations / test.iterations) * 100);

        // Small delay between requests to avoid overwhelming the model
        await new Promise(resolve => setTimeout(resolve, 100));

      } catch (error) {
        responses.push({
          success: false,
          responseTime: 0,
          error: error instanceof Error ? error.message : 'Request failed'
        });
        completedIterations++;
        setProgress((completedIterations / test.iterations) * 100);
      }
    }

    // Calculate statistics
    const successfulResponses = responses.filter(r => r.success);
    const successCount = successfulResponses.length;
    const failureCount = responses.length - successCount;
    
    const responseTimes = successfulResponses.map(r => r.responseTime);
    const averageResponseTime = responseTimes.length > 0 
      ? responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length 
      : 0;
    const minResponseTime = responseTimes.length > 0 ? Math.min(...responseTimes) : 0;
    const maxResponseTime = responseTimes.length > 0 ? Math.max(...responseTimes) : 0;
    
    const totalTime = responses.reduce((sum, r) => sum + r.responseTime, 0);
    const throughput = totalTime > 0 ? (successCount / (totalTime / 1000)) : 0;
    const errorRate = (failureCount / responses.length) * 100;

    return {
      testId: test.id,
      iterations: responses.length,
      successCount,
      failureCount,
      averageResponseTime,
      minResponseTime,
      maxResponseTime,
      throughput,
      errorRate,
      responses
    };
  }, [config, phase]);

  // Run selected benchmark tests
  const runBenchmarks = useCallback(async () => {
    if (selectedTests.length === 0) return;

    setBenchmarkRunning(true);
    setProgress(0);
    setCurrentTest(null);
    setResults([]);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const benchmarkResults: BenchmarkResult[] = [];

      for (const testId of selectedTests) {
        const test = availableTests.find(t => t.id === testId);
        if (!test || abortController.signal.aborted) continue;

        const result = await runBenchmarkTest(test, abortController.signal);
        benchmarkResults.push(result);
      }

      setResults(benchmarkResults);
      onBenchmarkComplete?.(benchmarkResults);

    } catch (error) {
      console.error('Benchmark failed:', error);
    } finally {
      setBenchmarkRunning(false);
      setCurrentTest(null);
      setProgress(0);
      abortControllerRef.current = null;
    }
  }, [selectedTests, availableTests, runBenchmarkTest, onBenchmarkComplete]);

  // Cancel benchmark
  const cancelBenchmark = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  // Format time
  const formatTime = (ms: number): string => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  // Get performance rating
  const getPerformanceRating = (avgTime: number): { rating: string; color: string } => {
    if (avgTime < 1000) return { rating: 'Excellent', color: 'text-green-600' };
    if (avgTime < 3000) return { rating: 'Good', color: 'text-blue-600' };
    if (avgTime < 10000) return { rating: 'Fair', color: 'text-yellow-600' };
    return { rating: 'Poor', color: 'text-red-600' };
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Benchmark Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Benchmark</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Model Info */}
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="font-medium">{config.backend} / {config.model}</div>
            <div className="text-sm text-gray-600">Phase: {phase}</div>
          </div>

          {/* Test Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Benchmark Tests
            </label>
            <div className="space-y-2">
              {availableTests.map(test => (
                <label key={test.id} className="flex items-start space-x-3">
                  <input
                    type="checkbox"
                    checked={selectedTests.includes(test.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedTests(prev => [...prev, test.id]);
                      } else {
                        setSelectedTests(prev => prev.filter(id => id !== test.id));
                      }
                    }}
                    className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    disabled={isRunning}
                  />
                  <div className="flex-1">
                    <div className="font-medium text-sm">{test.name}</div>
                    <div className="text-sm text-gray-600">{test.description}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {test.iterations} iterations, {formatTime(test.timeout)} timeout
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {selectedTests.length} test(s) selected
            </div>
            <div className="flex gap-2">
              {isRunning && (
                <Button onClick={cancelBenchmark} variant="outline" size="sm">
                  Cancel
                </Button>
              )}
              <Button
                onClick={runBenchmarks}
                disabled={isRunning || selectedTests.length === 0}
                loading={isRunning}
              >
                {isRunning ? 'Running...' : 'Run Benchmark'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Benchmark Progress */}
      {isRunning && (
        <Card>
          <CardContent className="p-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Benchmark Progress</span>
                <span className="text-sm text-gray-600">{progress.toFixed(0)}%</span>
              </div>
              <ProgressBar
                value={progress}
                variant="default"
                animated
                striped
              />
              {currentTest && (
                <div className="text-sm text-gray-600">
                  Running: {currentTest}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Benchmark Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          {results.map(result => {
            const test = availableTests.find(t => t.id === result.testId);
            const performance = getPerformanceRating(result.averageResponseTime);
            
            return (
              <Card key={result.testId}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {test?.name || result.testId}
                    <StatusBadge
                      status={result.errorRate < 10 ? 'completed' : result.errorRate < 50 ? 'running' : 'failed'}
                      label={`${result.successCount}/${result.iterations}`}
                    />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Performance Metrics */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="text-center">
                      <div className={cn('text-2xl font-bold', performance.color)}>
                        {formatTime(result.averageResponseTime)}
                      </div>
                      <div className="text-sm text-gray-600">Avg Response</div>
                      <div className={cn('text-xs', performance.color)}>
                        {performance.rating}
                      </div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {result.throughput.toFixed(1)}
                      </div>
                      <div className="text-sm text-gray-600">Req/sec</div>
                    </div>
                    
                    <div className="text-center">
                      <div className={cn(
                        'text-2xl font-bold',
                        result.errorRate < 10 ? 'text-green-600' : 
                        result.errorRate < 50 ? 'text-yellow-600' : 'text-red-600'
                      )}>
                        {result.errorRate.toFixed(1)}%
                      </div>
                      <div className="text-sm text-gray-600">Error Rate</div>
                    </div>
                    
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">
                        {formatTime(result.maxResponseTime - result.minResponseTime)}
                      </div>
                      <div className="text-sm text-gray-600">Time Range</div>
                    </div>
                  </div>

                  {/* Response Time Distribution */}
                  <div className="mb-4">
                    <div className="text-sm font-medium text-gray-700 mb-2">Response Time Distribution</div>
                    <div className="flex items-end gap-1 h-16">
                      {result.responses.slice(0, 20).map((response, index) => {
                        const height = result.maxResponseTime > 0 
                          ? (response.responseTime / result.maxResponseTime) * 100 
                          : 0;
                        
                        return (
                          <div
                            key={index}
                            className={cn(
                              'flex-1 rounded-t',
                              response.success ? 'bg-green-400' : 'bg-red-400'
                            )}
                            style={{ height: `${Math.max(height, 5)}%` }}
                            title={`${formatTime(response.responseTime)} - ${response.success ? 'Success' : 'Failed'}`}
                          />
                        );
                      })}
                    </div>
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>Min: {formatTime(result.minResponseTime)}</span>
                      <span>Max: {formatTime(result.maxResponseTime)}</span>
                    </div>
                  </div>

                  {/* Detailed Stats */}
                  <div className="text-sm text-gray-600 space-y-1">
                    <div>Total Iterations: {result.iterations}</div>
                    <div>Successful Requests: {result.successCount}</div>
                    <div>Failed Requests: {result.failureCount}</div>
                    <div>Min Response Time: {formatTime(result.minResponseTime)}</div>
                    <div>Max Response Time: {formatTime(result.maxResponseTime)}</div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};