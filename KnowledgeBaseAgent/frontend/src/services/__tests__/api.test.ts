import { describe, it, expect, beforeEach, vi } from 'vitest';
import { APIService, APIError } from '../api';

// Mock fetch
global.fetch = vi.fn();

describe('APIService', () => {
  let apiService: APIService;

  beforeEach(() => {
    apiService = new APIService('/api/v1');
    vi.clearAllMocks();
  });

  describe('GET requests', () => {
    it('should make successful GET request', async () => {
      const mockData = { id: '1', name: 'Test' };
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockData,
      });

      const result = await apiService.get('/test');
      
      expect(fetch).toHaveBeenCalledWith('/api/v1/test', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockData);
    });

    it('should handle query parameters', async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await apiService.get('/test', { page: 1, limit: 10, tags: ['a', 'b'] });
      
      expect(fetch).toHaveBeenCalledWith('/api/v1/test?page=1&limit=10&tags=a&tags=b', {
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  describe('POST requests', () => {
    it('should make successful POST request', async () => {
      const requestData = { name: 'Test' };
      const responseData = { id: '1', ...requestData };
      
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => responseData,
      });

      const result = await apiService.post('/test', requestData);
      
      expect(fetch).toHaveBeenCalledWith('/api/v1/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData),
      });
      expect(result).toEqual(responseData);
    });
  });

  describe('Error handling', () => {
    it('should throw APIError for HTTP errors', async () => {
      const errorResponse = {
        message: 'Not found',
        error_code: 'not_found',
        details: { resource: 'test' },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => errorResponse,
      });

      await expect(apiService.get('/test')).rejects.toThrow(APIError);
    });

    it('should handle network errors', async () => {
      (fetch as any).mockRejectedValueOnce(new Error('Network error'));

      await expect(apiService.get('/test')).rejects.toThrow(APIError);
    });
  });

  describe('Authentication', () => {
    it('should set auth token', () => {
      apiService.setAuthToken('test-token');
      expect(apiService['defaultHeaders']['Authorization']).toBe('Bearer test-token');
    });

    it('should set API key', () => {
      apiService.setAPIKey('test-key');
      expect(apiService['defaultHeaders']['X-API-Key']).toBe('test-key');
    });
  });
});