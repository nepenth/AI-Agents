import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useApi, useAsyncAction } from '../useApi';
import { APIError } from '@/services/api';

describe('useApi', () => {
  it('should handle successful API call', async () => {
    const mockApiCall = vi.fn().mockResolvedValue({ data: 'test' });
    
    const { result } = renderHook(() => useApi(mockApiCall));
    
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(null);
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toEqual({ data: 'test' });
    expect(result.current.error).toBe(null);
    expect(mockApiCall).toHaveBeenCalledTimes(1);
  });

  it('should handle API errors', async () => {
    const mockError = new APIError('Test error', 'test_error', 400);
    const mockApiCall = vi.fn().mockRejectedValue(mockError);
    
    const { result } = renderHook(() => useApi(mockApiCall));
    
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(mockError);
  });

  it('should refetch data', async () => {
    const mockApiCall = vi.fn()
      .mockResolvedValueOnce({ data: 'first' })
      .mockResolvedValueOnce({ data: 'second' });
    
    const { result } = renderHook(() => useApi(mockApiCall));
    
    await waitFor(() => {
      expect(result.current.data).toEqual({ data: 'first' });
    });
    
    await result.current.refetch();
    
    expect(result.current.data).toEqual({ data: 'second' });
    expect(mockApiCall).toHaveBeenCalledTimes(2);
  });
});

describe('useAsyncAction', () => {
  it('should execute action successfully', async () => {
    const mockAction = vi.fn().mockResolvedValue('success');
    
    const { result } = renderHook(() => useAsyncAction(mockAction));
    
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
    
    const promise = result.current.execute('arg1', 'arg2');
    
    expect(result.current.loading).toBe(true);
    
    const response = await promise;
    
    expect(result.current.loading).toBe(false);
    expect(response).toBe('success');
    expect(mockAction).toHaveBeenCalledWith('arg1', 'arg2');
  });

  it('should handle action errors', async () => {
    const mockError = new APIError('Action failed', 'action_error', 500);
    const mockAction = vi.fn().mockRejectedValue(mockError);
    
    const { result } = renderHook(() => useAsyncAction(mockAction));
    
    await expect(result.current.execute()).rejects.toThrow(mockError);
    
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(mockError);
  });
});