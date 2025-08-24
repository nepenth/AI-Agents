export interface CacheEntry<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
  key: string;
}

export interface CacheOptions {
  ttl?: number; // Time to live in milliseconds
  maxSize?: number; // Maximum number of entries
  serialize?: boolean; // Whether to serialize data to localStorage
  namespace?: string; // Namespace for localStorage keys
}

class CacheService {
  private memoryCache = new Map<string, CacheEntry<any>>();
  private defaultTTL = 5 * 60 * 1000; // 5 minutes
  private maxSize = 100;
  private namespace = 'ai-agent-cache';

  constructor(options: CacheOptions = {}) {
    this.defaultTTL = options.ttl || this.defaultTTL;
    this.maxSize = options.maxSize || this.maxSize;
    this.namespace = options.namespace || this.namespace;

    // Clean up expired entries periodically
    setInterval(() => this.cleanup(), 60000); // Every minute
  }

  // Set cache entry
  set<T>(key: string, data: T, options: CacheOptions = {}): void {
    const ttl = options.ttl || this.defaultTTL;
    const now = Date.now();
    
    const entry: CacheEntry<T> = {
      data,
      timestamp: now,
      expiresAt: now + ttl,
      key
    };

    // Add to memory cache
    this.memoryCache.set(key, entry);

    // Add to localStorage if serialization is enabled
    if (options.serialize && this.canUseLocalStorage()) {
      try {
        const serialized = JSON.stringify(entry);
        localStorage.setItem(`${this.namespace}:${key}`, serialized);
      } catch (error) {
        console.warn('Failed to serialize cache entry to localStorage:', error);
      }
    }

    // Enforce max size
    this.enforceMaxSize();
  }

  // Get cache entry
  get<T>(key: string, options: CacheOptions = {}): T | null {
    // Try memory cache first
    let entry = this.memoryCache.get(key);

    // Try localStorage if not in memory and serialization is enabled
    if (!entry && options.serialize && this.canUseLocalStorage()) {
      try {
        const serialized = localStorage.getItem(`${this.namespace}:${key}`);
        if (serialized) {
          entry = JSON.parse(serialized);
          // Add back to memory cache
          if (entry) {
            this.memoryCache.set(key, entry);
          }
        }
      } catch (error) {
        console.warn('Failed to deserialize cache entry from localStorage:', error);
      }
    }

    if (!entry) {
      return null;
    }

    // Check if expired
    if (Date.now() > entry.expiresAt) {
      this.delete(key);
      return null;
    }

    return entry.data;
  }

  // Check if key exists and is not expired
  has(key: string): boolean {
    return this.get(key) !== null;
  }

  // Delete cache entry
  delete(key: string): void {
    this.memoryCache.delete(key);
    
    if (this.canUseLocalStorage()) {
      localStorage.removeItem(`${this.namespace}:${key}`);
    }
  }

  // Clear all cache entries
  clear(): void {
    this.memoryCache.clear();
    
    if (this.canUseLocalStorage()) {
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith(`${this.namespace}:`)) {
          localStorage.removeItem(key);
        }
      });
    }
  }

  // Get cache statistics
  getStats(): {
    size: number;
    maxSize: number;
    hitRate: number;
    memoryUsage: number;
  } {
    const memoryUsage = this.estimateMemoryUsage();
    
    return {
      size: this.memoryCache.size,
      maxSize: this.maxSize,
      hitRate: this.calculateHitRate(),
      memoryUsage
    };
  }

  // Get all cache keys
  keys(): string[] {
    return Array.from(this.memoryCache.keys());
  }

  // Get cache entries by pattern
  getByPattern(pattern: RegExp): Array<{ key: string; data: any }> {
    const results: Array<{ key: string; data: any }> = [];
    
    for (const [key, entry] of this.memoryCache.entries()) {
      if (pattern.test(key) && Date.now() <= entry.expiresAt) {
        results.push({ key, data: entry.data });
      }
    }
    
    return results;
  }

  // Invalidate cache entries by pattern
  invalidateByPattern(pattern: RegExp): void {
    const keysToDelete: string[] = [];
    
    for (const key of this.memoryCache.keys()) {
      if (pattern.test(key)) {
        keysToDelete.push(key);
      }
    }
    
    keysToDelete.forEach(key => this.delete(key));
  }

  // Cache with automatic refresh
  async getOrFetch<T>(
    key: string,
    fetchFn: () => Promise<T>,
    options: CacheOptions = {}
  ): Promise<T> {
    // Try to get from cache first
    const cached = this.get<T>(key, options);
    if (cached !== null) {
      return cached;
    }

    // Fetch new data
    try {
      const data = await fetchFn();
      this.set(key, data, options);
      return data;
    } catch (error) {
      // If fetch fails, try to return stale data if available
      const staleEntry = this.memoryCache.get(key);
      if (staleEntry) {
        console.warn(`Using stale cache data for ${key} due to fetch error:`, error);
        return staleEntry.data;
      }
      throw error;
    }
  }

  // Cache with background refresh
  async getWithBackgroundRefresh<T>(
    key: string,
    fetchFn: () => Promise<T>,
    options: CacheOptions = {}
  ): Promise<T> {
    const cached = this.get<T>(key, options);
    
    if (cached !== null) {
      // Return cached data immediately
      // But refresh in background if it's getting stale
      const entry = this.memoryCache.get(key);
      if (entry) {
        const age = Date.now() - entry.timestamp;
        const ttl = options.ttl || this.defaultTTL;
        
        // Refresh if more than 50% of TTL has passed
        if (age > ttl * 0.5) {
          fetchFn().then(data => {
            this.set(key, data, options);
          }).catch(error => {
            console.warn(`Background refresh failed for ${key}:`, error);
          });
        }
      }
      
      return cached;
    }

    // No cached data, fetch synchronously
    const data = await fetchFn();
    this.set(key, data, options);
    return data;
  }

  // Preload cache entries
  async preload<T>(
    entries: Array<{ key: string; fetchFn: () => Promise<T>; options?: CacheOptions }>
  ): Promise<void> {
    const promises = entries.map(async ({ key, fetchFn, options = {} }) => {
      try {
        const data = await fetchFn();
        this.set(key, data, options);
      } catch (error) {
        console.warn(`Failed to preload cache entry ${key}:`, error);
      }
    });

    await Promise.allSettled(promises);
  }

  // Private methods
  private cleanup(): void {
    const now = Date.now();
    const expiredKeys: string[] = [];

    for (const [key, entry] of this.memoryCache.entries()) {
      if (now > entry.expiresAt) {
        expiredKeys.push(key);
      }
    }

    expiredKeys.forEach(key => this.delete(key));
  }

  private enforceMaxSize(): void {
    if (this.memoryCache.size <= this.maxSize) {
      return;
    }

    // Remove oldest entries first
    const entries = Array.from(this.memoryCache.entries());
    entries.sort((a, b) => a[1].timestamp - b[1].timestamp);

    const toRemove = entries.slice(0, this.memoryCache.size - this.maxSize);
    toRemove.forEach(([key]) => this.delete(key));
  }

  private canUseLocalStorage(): boolean {
    try {
      return typeof localStorage !== 'undefined' && localStorage !== null;
    } catch {
      return false;
    }
  }

  private estimateMemoryUsage(): number {
    let size = 0;
    
    for (const entry of this.memoryCache.values()) {
      try {
        size += JSON.stringify(entry).length * 2; // Rough estimate (UTF-16)
      } catch {
        size += 1000; // Fallback estimate
      }
    }
    
    return size;
  }

  private hitCount = 0;
  private missCount = 0;

  private calculateHitRate(): number {
    const total = this.hitCount + this.missCount;
    return total > 0 ? this.hitCount / total : 0;
  }

  // Update hit/miss counters (called internally)
  private recordHit(): void {
    this.hitCount++;
  }

  private recordMiss(): void {
    this.missCount++;
  }
}

// Create specialized cache instances
export const apiCache = new CacheService({
  ttl: 5 * 60 * 1000, // 5 minutes
  maxSize: 100,
  namespace: 'api-cache'
});

export const userCache = new CacheService({
  ttl: 30 * 60 * 1000, // 30 minutes
  maxSize: 50,
  serialize: true,
  namespace: 'user-cache'
});

export const systemCache = new CacheService({
  ttl: 60 * 1000, // 1 minute
  maxSize: 20,
  namespace: 'system-cache'
});

// React hook for using cache
export function useCache<T>(
  key: string,
  fetchFn: () => Promise<T>,
  options: CacheOptions & { 
    enabled?: boolean;
    backgroundRefresh?: boolean;
    cache?: CacheService;
  } = {}
) {
  const [data, setData] = React.useState<T | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<Error | null>(null);
  
  const cache = options.cache || apiCache;
  const enabled = options.enabled !== false;
  const backgroundRefresh = options.backgroundRefresh || false;

  const fetchData = React.useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError(null);

    try {
      const result = backgroundRefresh
        ? await cache.getWithBackgroundRefresh(key, fetchFn, options)
        : await cache.getOrFetch(key, fetchFn, options);
      
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [key, fetchFn, enabled, backgroundRefresh, cache, options]);

  React.useEffect(() => {
    fetchData();
  }, [fetchData]);

  const invalidate = React.useCallback(() => {
    cache.delete(key);
    fetchData();
  }, [cache, key, fetchData]);

  const refresh = React.useCallback(() => {
    cache.delete(key);
    return fetchData();
  }, [cache, key, fetchData]);

  return {
    data,
    loading,
    error,
    invalidate,
    refresh,
    isStale: data !== null && !cache.has(key)
  };
}

export { CacheService };