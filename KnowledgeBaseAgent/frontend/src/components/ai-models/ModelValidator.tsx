import React, { useState, useCallback, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { StatusBadge } from '../ui/StatusBadge';
import { ProgressBar } from '../ui/ProgressBar';
import { aiModelService } from '../../services/aiModelService';
import { cn } from '../../utils/cn';
import type { 
  ModelPhase, 
  PhaseModelConfig, 
  ModelTestResult,
  ModelBackend,
  AvailableModels
} from '../../services/aiModelService';

export interface ValidationTest {
  id: string;
  name: string;
  description: string;
  phase: ModelPhase;
  prompt: string;
  expectedCapabilities: string[];
  timeout: number;
}

export interface ValidationResult {
  testId: string;
  success: boolean;
  responseTime: number;
  error?: string;
  response?: any;
  capabilities: string[];
  score: number; // 0-100
}

export interface ModelValidatorProps {
  availableModels: AvailableModels;
  currentConfig: Record<ModelPhase, PhaseModelConfig | null>;
  onValidationComplete?: (results: Record<string, ValidationResult[]>) => void;
  className?: string;
}

const VALIDATION_TESTS: ValidationTest[] = [
  // Vision Tests
  {
    id: 'vision_basic',
    name: 'Basic Image Analysis',
    description: 'Test ability to analyze and describe images',
    phase: 'vision',
    prompt: 'Analyze this image and describe what you see in detail.',
    expectedCapabilities: ['vision', 'multimodal'],
    timeout: 30000
  },
  {
    id: 'vision_text_extraction',
    name: 'Text Extraction',
    description: 'Test ability to extract text from images',
    phase: 'vision',
    prompt: 'Extract and transcribe any text visible in this image.',
    expectedCapabilities: ['vision', 'ocr'],
    timeout: 30000
  },
  
  // Knowledge Generation Tests
  {
    id: 'kb_summarization',
    name: 'Content Summarization',
    description: 'Test ability to summarize complex content',
    phase: 'kb_generation',
    prompt: 'Summarize this content in 2-3 sentences: "Artificial intelligence and machine learning are rapidly transforming industries across the globe. From healthcare to finance, these technologies are enabling new capabilities and efficiencies that were previously impossible."',
    expectedCapabilities: ['text', 'instruct'],
    timeout: 15000
  },
  {
    id: 'kb_categorization',
    name: 'Content Categorization',
    description: 'Test ability to categorize and tag content',
    phase: 'kb_generation',
    prompt: 'Categorize this tweet and suggest 3 relevant tags: "Just deployed our new ML model to production! Seeing 15% improvement in accuracy. #MachineLearning #AI #Tech"',
    expectedCapabilities: ['text', 'instruct'],
    timeout: 15000
  },
  
  // Synthesis Tests
  {
    id: 'synthesis_connection',
    name: 'Content Synthesis',
    description: 'Test ability to synthesize related content',
    phase: 'synthesis',
    prompt: 'Create a synthesis connecting these topics: 1) AI ethics and bias, 2) Automated decision making, 3) Regulatory compliance. Explain how they relate.',
    expectedCapabilities: ['text', 'instruct'],
    timeout: 20000
  },
  
  // Chat Tests
  {
    id: 'chat_conversation',
    name: 'Conversational Response',
    description: 'Test conversational AI capabilities',
    phase: 'chat',
    prompt: 'Hello! I\'m interested in learning about AI. Can you explain machine learning in simple terms?',
    expectedCapabilities: ['text', 'instruct', 'chat'],
    timeout: 15000
  },
  {
    id: 'chat_context',
    name: 'Context Awareness',
    description: 'Test ability to maintain context in conversation',
    phase: 'chat',
    prompt: 'Following up on machine learning - what are some practical applications I might encounter in daily life?',
    expectedCapabilities: ['text', 'instruct', 'chat'],
    timeout: 15000
  },
  
  // Embeddings Tests
  {
    id: 'embeddings_generation',
    name: 'Vector Generation',
    description: 'Test ability to generate vector embeddings',
    phase: 'embeddings',
    prompt: 'artificial intelligence and machine learning',
    expectedCapabilities: ['embed', 'embeddings'],
    timeout: 10000
  }
];

export const ModelValidator: React.FC<ModelValidatorProps> = ({
  availableModels,
  currentConfig,
  onValidationComplete,
  className
}) => {
  const [isValidating, setIsValidating] = useState(false);
  const [validationProgress, setValidationProgress] = useState(0);
  const [currentTest, setCurrentTest] = useState<string | null>(null);
  const [validationResults, setValidationResults] = useState<Record<string, ValidationResult[]>>({});
  const [selectedPhases, setSelectedPhases] = useState<ModelPhase[]>([]);
  const [validationMode, setValidationMode] = useState<'quick' | 'comprehensive'>('quick');

  // Get configured phases
  const configuredPhases = Object.entries(currentConfig)
    .filter(([, config]) => config !== null)
    .map(([phase]) => phase as ModelPhase);

  // Initialize selected phases
  useEffect(() => {
    if (selectedPhases.length === 0 && configuredPhases.length > 0) {
      setSelectedPhases(configuredPhases);
    }
  }, [configuredPhases, selectedPhases.length]);

  // Get tests for selected phases
  const getTestsForValidation = useCallback(() => {
    const tests = VALIDATION_TESTS.filter(test => selectedPhases.includes(test.phase));
    
    if (validationMode === 'quick') {
      // For quick validation, run one test per phase
      const quickTests: ValidationTest[] = [];
      selectedPhases.forEach(phase => {
        const phaseTests = tests.filter(t => t.phase === phase);
        if (phaseTests.length > 0) {
          quickTests.push(phaseTests[0]); // Take first test for each phase
        }
      });
      return quickTests;
    }
    
    return tests; // Comprehensive mode runs all tests
  }, [selectedPhases, validationMode]);

  // Run validation for a single model
  const validateModel = useCallback(async (
    phase: ModelPhase,
    config: PhaseModelConfig,
    tests: ValidationTest[]
  ): Promise<ValidationResult[]> => {
    const results: ValidationResult[] = [];
    
    for (const test of tests) {
      if (test.phase !== phase) continue;
      
      setCurrentTest(`${phase}: ${test.name}`);
      
      try {
        const startTime = Date.now();
        const testResult = await aiModelService.testModel(
          config.backend,
          config.model,
          phase,
          test.prompt
        );
        const responseTime = Date.now() - startTime;
        
        // Calculate score based on success, response time, and capabilities
        let score = 0;
        if (testResult.success) {
          score += 60; // Base score for success
          
          // Response time scoring (40 points max)
          if (responseTime < 2000) score += 40;
          else if (responseTime < 5000) score += 30;
          else if (responseTime < 10000) score += 20;
          else if (responseTime < test.timeout) score += 10;
          
          // Capability matching (bonus points)
          const matchedCapabilities = test.expectedCapabilities.filter(expected =>
            testResult.capabilities.some(actual => 
              actual.toLowerCase().includes(expected.toLowerCase()) ||
              expected.toLowerCase().includes(actual.toLowerCase())
            )
          );
          score = Math.min(100, score + (matchedCapabilities.length * 5));
        }
        
        results.push({
          testId: test.id,
          success: testResult.success,
          responseTime,
          error: testResult.error,
          response: testResult.response,
          capabilities: testResult.capabilities,
          score
        });
        
      } catch (error) {
        results.push({
          testId: test.id,
          success: false,
          responseTime: 0,
          error: error instanceof Error ? error.message : 'Test failed',
          capabilities: [],
          score: 0
        });
      }
    }
    
    return results;
  }, []);

  // Run full validation
  const runValidation = useCallback(async () => {
    if (selectedPhases.length === 0) return;
    
    setIsValidating(true);
    setValidationProgress(0);
    setCurrentTest(null);
    
    const tests = getTestsForValidation();
    const results: Record<string, ValidationResult[]> = {};
    
    let completedTests = 0;
    const totalTests = selectedPhases.reduce((count, phase) => {
      const config = currentConfig[phase];
      return config ? count + tests.filter(t => t.phase === phase).length : count;
    }, 0);
    
    try {
      for (const phase of selectedPhases) {
        const config = currentConfig[phase];
        if (!config) continue;
        
        const phaseTests = tests.filter(t => t.phase === phase);
        const phaseResults = await validateModel(phase, config, phaseTests);
        
        const key = `${phase}_${config.backend}_${config.model}`;
        results[key] = phaseResults;
        
        completedTests += phaseTests.length;
        setValidationProgress((completedTests / totalTests) * 100);
      }
      
      setValidationResults(results);
      onValidationComplete?.(results);
      
    } catch (error) {
      console.error('Validation failed:', error);
    } finally {
      setIsValidating(false);
      setCurrentTest(null);
      setValidationProgress(0);
    }
  }, [selectedPhases, currentConfig, getTestsForValidation, validateModel, onValidationComplete]);

  // Calculate overall validation score
  const getOverallScore = useCallback(() => {
    const allResults = Object.values(validationResults).flat();
    if (allResults.length === 0) return 0;
    
    const totalScore = allResults.reduce((sum, result) => sum + result.score, 0);
    return Math.round(totalScore / allResults.length);
  }, [validationResults]);

  // Get validation summary
  const getValidationSummary = useCallback(() => {
    const allResults = Object.values(validationResults).flat();
    const passed = allResults.filter(r => r.success).length;
    const total = allResults.length;
    const avgResponseTime = allResults.length > 0 
      ? allResults.reduce((sum, r) => sum + r.responseTime, 0) / allResults.length 
      : 0;
    
    return { passed, total, avgResponseTime };
  }, [validationResults]);

  const overallScore = getOverallScore();
  const summary = getValidationSummary();

  return (
    <div className={cn('space-y-6', className)}>
      {/* Validation Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Model Validation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Phase Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Phases to Validate
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {configuredPhases.map(phase => (
                <label key={phase} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={selectedPhases.includes(phase)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedPhases(prev => [...prev, phase]);
                      } else {
                        setSelectedPhases(prev => prev.filter(p => p !== phase));
                      }
                    }}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm capitalize">{phase.replace('_', ' ')}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Validation Mode */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Validation Mode
            </label>
            <div className="flex gap-4">
              <label className="flex items-center space-x-2">
                <input
                  type="radio"
                  value="quick"
                  checked={validationMode === 'quick'}
                  onChange={(e) => setValidationMode(e.target.value as 'quick')}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm">Quick (1 test per phase)</span>
              </label>
              <label className="flex items-center space-x-2">
                <input
                  type="radio"
                  value="comprehensive"
                  checked={validationMode === 'comprehensive'}
                  onChange={(e) => setValidationMode(e.target.value as 'comprehensive')}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm">Comprehensive (all tests)</span>
              </label>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {getTestsForValidation().length} tests will be run across {selectedPhases.length} phases
            </div>
            <Button
              onClick={runValidation}
              disabled={isValidating || selectedPhases.length === 0}
              loading={isValidating}
            >
              {isValidating ? 'Validating...' : 'Run Validation'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Validation Progress */}
      {isValidating && (
        <Card>
          <CardContent className="p-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Validation Progress</span>
                <span className="text-sm text-gray-600">{validationProgress.toFixed(0)}%</span>
              </div>
              <ProgressBar
                value={validationProgress}
                variant="default"
                animated
                striped
              />
              {currentTest && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <LoadingSpinner size="sm" />
                  <span>Running: {currentTest}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Validation Results Summary */}
      {Object.keys(validationResults).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Validation Results
              <StatusBadge
                status={overallScore >= 80 ? 'completed' : overallScore >= 60 ? 'running' : 'failed'}
                label={`${overallScore}/100`}
              />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{summary.passed}</div>
                <div className="text-sm text-gray-600">Tests Passed</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{summary.total}</div>
                <div className="text-sm text-gray-600">Total Tests</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {summary.avgResponseTime > 0 ? `${(summary.avgResponseTime / 1000).toFixed(1)}s` : 'N/A'}
                </div>
                <div className="text-sm text-gray-600">Avg Response</div>
              </div>
            </div>

            {/* Detailed Results */}
            <div className="space-y-4">
              {Object.entries(validationResults).map(([key, results]) => {
                const [phase, backend, model] = key.split('_');
                const avgScore = results.reduce((sum, r) => sum + r.score, 0) / results.length;
                const passedTests = results.filter(r => r.success).length;
                
                return (
                  <div key={key} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="font-medium">{phase} / {backend} / {model}</div>
                        <div className="text-sm text-gray-600">
                          {passedTests}/{results.length} tests passed
                        </div>
                      </div>
                      <StatusBadge
                        status={avgScore >= 80 ? 'completed' : avgScore >= 60 ? 'running' : 'failed'}
                        label={`${Math.round(avgScore)}/100`}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      {results.map(result => {
                        const test = VALIDATION_TESTS.find(t => t.id === result.testId);
                        return (
                          <div
                            key={result.testId}
                            className={cn(
                              'flex items-center justify-between p-2 rounded text-sm',
                              result.success ? 'bg-green-50' : 'bg-red-50'
                            )}
                          >
                            <div className="flex items-center gap-2">
                              <span>{result.success ? '✅' : '❌'}</span>
                              <span>{test?.name || result.testId}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-gray-600">
                                {result.responseTime > 0 ? `${result.responseTime}ms` : ''}
                              </span>
                              <span className={cn(
                                'font-medium',
                                result.score >= 80 ? 'text-green-600' :
                                result.score >= 60 ? 'text-yellow-600' :
                                'text-red-600'
                              )}>
                                {result.score}/100
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
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