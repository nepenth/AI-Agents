import { useState, useEffect, useCallback } from 'react';
import { APIError } from '@/services/api';

export interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: APIError | null;
  refetch: () => Promise<void>;
}

export function useApi<T>(
  apiCall: () => Promise<T>,
  dependencies: any[] = []
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<APIError | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await apiCall();
      setData(result);
    } catch (err) {
      setError(err instanceof APIError ? err : new APIError(
        'Unknown error',
        'unknown_error',
        0
      ));
    } finally {
      setLoading(false);
    }
  }, dependencies);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
  };
}

export function useAsyncAction<T, P extends any[]>(
  action: (...args: P) => Promise<T>
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<APIError | null>(null);

  const execute = useCallback(async (...args: P): Promise<T | null> => {
    setLoading(true);
    setError(null);

    try {
      const result = await action(...args);
      return result;
    } catch (err) {
      const apiError = err instanceof APIError ? err : new APIError(
        'Unknown error',
        'unknown_error',
        0
      );
      setError(apiError);
      throw apiError;
    } finally {
      setLoading(false);
    }
  }, [action]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    execute,
    loading,
    error,
    clearError,
  };
}