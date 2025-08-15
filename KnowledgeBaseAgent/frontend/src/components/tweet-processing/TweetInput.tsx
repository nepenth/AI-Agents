import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { tweetService } from '../../services/tweetService';
import { cn } from '../../utils/cn';

export interface TweetInputProps {
  onTweetSubmit: (tweetId: string, options?: ProcessingOptions) => void;
  isProcessing?: boolean;
  className?: string;
}

export interface ProcessingOptions {
  forceReprocess?: boolean;
  phases?: string[];
  aiModelOverrides?: { [phase: string]: string };
}

export const TweetInput: React.FC<TweetInputProps> = ({
  onTweetSubmit,
  isProcessing = false,
  className
}) => {
  const [input, setInput] = useState('');
  const [extractedTweetId, setExtractedTweetId] = useState<string | null>(null);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<ProcessingOptions>({
    forceReprocess: false,
    phases: [],
    aiModelOverrides: {}
  });
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);

  const validateInput = useCallback((value: string) => {
    if (!value.trim()) {
      setIsValid(null);
      setExtractedTweetId(null);
      setError(null);
      return;
    }

    // Try to extract tweet ID from URL
    const extractedId = tweetService.extractTweetIdFromUrl(value);
    const tweetId = extractedId || value.trim();

    if (tweetService.validateTweetId(tweetId)) {
      setIsValid(true);
      setExtractedTweetId(tweetId);
      setError(null);
    } else {
      setIsValid(false);
      setExtractedTweetId(null);
      setError('Please enter a valid tweet ID or Twitter URL');
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);
    validateInput(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!extractedTweetId || !isValid) {
      setError('Please enter a valid tweet ID or URL');
      return;
    }

    onTweetSubmit(extractedTweetId, options);
  };

  const handlePasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setInput(text);
      validateInput(text);
    } catch (error) {
      console.error('Failed to read from clipboard:', error);
      setError('Failed to read from clipboard');
    }
  };

  const handleClearInput = () => {
    setInput('');
    setExtractedTweetId(null);
    setIsValid(null);
    setError(null);
  };

  const availablePhases = [
    { id: 'phase_1', name: 'System Initialization' },
    { id: 'phase_2', name: 'Fetch Bookmarks' },
    { id: 'phase_2_1', name: 'Bookmark Caching' },
    { id: 'phase_3_1', name: 'Media Analysis' },
    { id: 'phase_3_2', name: 'Content Understanding' },
    { id: 'phase_3_3', name: 'AI Categorization' },
    { id: 'phase_4', name: 'Synthesis Generation' },
    { id: 'phase_5', name: 'Embedding Generation' },
    { id: 'phase_6', name: 'README Generation' },
    { id: 'phase_7', name: 'Git Sync' }
  ];

  const handlePhaseToggle = (phaseId: string) => {
    setOptions(prev => ({
      ...prev,
      phases: prev.phases?.includes(phaseId)
        ? prev.phases.filter(id => id !== phaseId)
        : [...(prev.phases || []), phaseId]
    }));
  };

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Process Tweet</span>
          <div className="flex items-center gap-2">
            {isValid === true && (
              <span className="text-green-600 text-sm">✅ Valid</span>
            )}
            {isValid === false && (
              <span className="text-red-600 text-sm">❌ Invalid</span>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Main Input */}
          <div className="space-y-2">
            <label htmlFor="tweet-input" className="text-sm font-medium text-gray-700">
              Tweet ID or URL
            </label>
            <div className="relative">
              <input
                id="tweet-input"
                type="text"
                value={input}
                onChange={handleInputChange}
                placeholder="Enter tweet ID (e.g., 1955505151680319929) or URL (https://twitter.com/user/status/...)"
                className={cn(
                  'w-full px-3 py-2 pr-20 border rounded-md focus:outline-none focus:ring-2 transition-colors',
                  isValid === true && 'border-green-300 focus:ring-green-500',
                  isValid === false && 'border-red-300 focus:ring-red-500',
                  isValid === null && 'border-gray-300 focus:ring-blue-500'
                )}
                disabled={isProcessing}
              />
              <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex gap-1">
                {input && (
                  <button
                    type="button"
                    onClick={handleClearInput}
                    className="text-gray-400 hover:text-gray-600 p-1"
                    disabled={isProcessing}
                  >
                    ✕
                  </button>
                )}
                <button
                  type="button"
                  onClick={handlePasteFromClipboard}
                  className="text-gray-400 hover:text-gray-600 p-1"
                  disabled={isProcessing}
                  title="Paste from clipboard"
                >
                  📋
                </button>
              </div>
            </div>
            
            {/* Extracted Tweet ID Display */}
            {extractedTweetId && extractedTweetId !== input.trim() && (
              <div className="text-sm text-blue-600 bg-blue-50 p-2 rounded border">
                <strong>Extracted Tweet ID:</strong> {extractedTweetId}
              </div>
            )}
            
            {/* Error Display */}
            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded border">
                {error}
              </div>
            )}
          </div>

          {/* Advanced Options Toggle */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
              disabled={isProcessing}
            >
              {showAdvancedOptions ? 'Hide' : 'Show'} Advanced Options
            </button>
          </div>

          {/* Advanced Options */}
          {showAdvancedOptions && (
            <div className="space-y-4 p-4 bg-gray-50 rounded-lg border">
              {/* Force Reprocess */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="force-reprocess"
                  checked={options.forceReprocess || false}
                  onChange={(e) => setOptions(prev => ({
                    ...prev,
                    forceReprocess: e.target.checked
                  }))}
                  disabled={isProcessing}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="force-reprocess" className="text-sm text-gray-700">
                  Force reprocess (ignore cached results)
                </label>
              </div>

              {/* Phase Selection */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">
                  Select specific phases to run (leave empty for all phases):
                </label>
                <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                  {availablePhases.map(phase => (
                    <div key={phase.id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id={`phase-${phase.id}`}
                        checked={options.phases?.includes(phase.id) || false}
                        onChange={() => handlePhaseToggle(phase.id)}
                        disabled={isProcessing}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <label 
                        htmlFor={`phase-${phase.id}`} 
                        className="text-xs text-gray-600 cursor-pointer"
                      >
                        {phase.name}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* AI Model Overrides */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">
                  AI Model Overrides (optional):
                </label>
                <div className="text-xs text-gray-500 mb-2">
                  Override specific AI models for phases. Leave empty to use default configuration.
                </div>
                <div className="space-y-2">
                  {['vision', 'kb_generation', 'synthesis', 'chat', 'embeddings'].map(phase => (
                    <div key={phase} className="flex items-center gap-2">
                      <label className="text-xs text-gray-600 w-24 capitalize">
                        {phase.replace('_', ' ')}:
                      </label>
                      <input
                        type="text"
                        placeholder="e.g., llama2, gpt-3.5-turbo"
                        value={options.aiModelOverrides?.[phase] || ''}
                        onChange={(e) => setOptions(prev => ({
                          ...prev,
                          aiModelOverrides: {
                            ...prev.aiModelOverrides,
                            [phase]: e.target.value
                          }
                        }))}
                        disabled={isProcessing}
                        className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={!isValid || isProcessing}
              loading={isProcessing}
              className="flex-1"
            >
              {isProcessing ? 'Processing...' : 'Start Processing'}
            </Button>
            
            {/* Quick Actions */}
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setInput('1955505151680319929'); // Example tweet ID
                validateInput('1955505151680319929');
              }}
              disabled={isProcessing}
              className="px-4"
            >
              Example
            </Button>
          </div>

          {/* Processing Info */}
          {isProcessing && (
            <div className="text-sm text-blue-600 bg-blue-50 p-3 rounded border">
              <div className="flex items-center gap-2">
                <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                <span>Processing tweet through the seven-phase pipeline...</span>
              </div>
              <div className="text-xs text-blue-500 mt-1">
                This may take a few minutes depending on the content complexity and AI model availability.
              </div>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
};