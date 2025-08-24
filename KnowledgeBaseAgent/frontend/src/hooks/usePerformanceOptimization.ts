import { useCallback, useMemo, useRef, useEffect, useState } from 'react';
import { performanceService } from '@/services/performanceService';

// Hook for debouncing values
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// Hook for throttling function calls
export function useThrottle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): T {
  const inThrottle = useRef<boolean>(false);
  
  return useCallback(
    ((...args: any[]) => {
      if (!inThrottle.current) {
        func.apply(null, args);
        inThrottle.current = true;
        setTimeout(() => {
          inThrottle.current = false;
        }, limit);
      }
    }) as T,
    [func, limit]
  );
}

// Hook for lazy loading with Intersection Observer
export function useLazyLoading(
  threshold: number = 0.1,
  rootMargin: string = '50px'
) {
  const [isVisible, setIsVisible] = useState(false);
  const [hasBeenVisible, setHasBeenVisible] = useState(false);
  const elementRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = performanceService.createIntersectionObserver(
      (entries) => {
        const [entry] = entries;
        const visible = entry.isIntersecting;
        setIsVisible(visible);
        
        if (visible && !hasBeenVisible) {
          setHasBeenVisible(true);
        }
      },
      { threshold, rootMargin }
    );

    if (observer && elementRef.current) {
      observer.observe(elementRef.current);
    }

    return () => {
      if (observer && elementRef.current) {
        observer.unobserve(elementRef.current);
      }
    };
  }, [threshold, rootMargin, hasBeenVisible]);

  return { elementRef, isVisible, hasBeenVisible };
}

// Hook for virtual scrolling
export function useVirtualScrolling<T>(
  items: T[],
  itemHeight: number,
  containerHeight: number,
  overscan: number = 5
) {
  const [scrollTop, setScrollTop] = useState(0);

  const visibleRange = useMemo(() => {
    const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const visibleCount = Math.ceil(containerHeight / itemHeight);
    const end = Math.min(items.length, start + visibleCount + overscan * 2);
    
    return { start, end };
  }, [scrollTop, itemHeight, containerHeight, items.length, overscan]);

  const visibleItems = useMemo(() => {
    return items.slice(visibleRange.start, visibleRange.end).map((item, index) => ({
      item,
      index: visibleRange.start + index,
      style: {
        position: 'absolute' as const,
        top: (visibleRange.start + index) * itemHeight,
        height: itemHeight,
        width: '100%'
      }
    }));
  }, [items, visibleRange, itemHeight]);

  const totalHeight = items.length * itemHeight;

  const handleScroll = useThrottle((event: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  }, 16); // ~60fps

  return {
    visibleItems,
    totalHeight,
    handleScroll,
    containerProps: {
      style: { height: containerHeight, overflow: 'auto' },
      onScroll: handleScroll
    }
  };
}

// Hook for memoizing expensive calculations
export function useExpensiveMemo<T>(
  factory: () => T,
  deps: React.DependencyList,
  componentName?: string
): T {
  return useMemo(() => {
    if (componentName) {
      return performanceService.measureComponentRender(
        `${componentName}-memo`,
        factory
      );
    }
    return factory();
  }, deps);
}

// Hook for measuring component render performance
export function useRenderPerformance(componentName: string) {
  const renderCount = useRef(0);
  const lastRenderTime = useRef(0);

  useEffect(() => {
    renderCount.current += 1;
    const now = performance.now();
    
    if (lastRenderTime.current > 0) {
      const timeSinceLastRender = now - lastRenderTime.current;
      
      if (timeSinceLastRender < 16) { // Less than one frame
        console.warn(
          `${componentName} re-rendered too quickly: ${timeSinceLastRender}ms (render #${renderCount.current})`
        );
      }
    }
    
    lastRenderTime.current = now;
  });

  return {
    renderCount: renderCount.current,
    measureRender: <T>(fn: () => T): T => 
      performanceService.measureComponentRender(componentName, fn)
  };
}

// Hook for optimizing API calls
export function useOptimizedApi() {
  const requestCache = useRef(new Map<string, Promise<any>>());
  const abortControllers = useRef(new Map<string, AbortController>());

  const makeRequest = useCallback(async <T>(
    key: string,
    requestFn: (signal: AbortSignal) => Promise<T>,
    cacheTime: number = 5000
  ): Promise<T> => {
    // Check cache first
    const cachedRequest = requestCache.current.get(key);
    if (cachedRequest) {
      return cachedRequest;
    }

    // Cancel any existing request for this key
    const existingController = abortControllers.current.get(key);
    if (existingController) {
      existingController.abort();
    }

    // Create new abort controller
    const controller = new AbortController();
    abortControllers.current.set(key, controller);

    // Make the request with performance measurement
    const requestPromise = performanceService.measureApiCall(
      key,
      () => requestFn(controller.signal)
    );

    // Cache the promise
    requestCache.current.set(key, requestPromise);

    // Set up cache cleanup
    setTimeout(() => {
      requestCache.current.delete(key);
      abortControllers.current.delete(key);
    }, cacheTime);

    try {
      const result = await requestPromise;
      return result;
    } catch (error) {
      // Remove from cache on error
      requestCache.current.delete(key);
      abortControllers.current.delete(key);
      throw error;
    }
  }, []);

  const cancelRequest = useCallback((key: string) => {
    const controller = abortControllers.current.get(key);
    if (controller) {
      controller.abort();
      abortControllers.current.delete(key);
      requestCache.current.delete(key);
    }
  }, []);

  const clearCache = useCallback(() => {
    // Cancel all pending requests
    abortControllers.current.forEach(controller => controller.abort());
    
    // Clear caches
    requestCache.current.clear();
    abortControllers.current.clear();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearCache();
    };
  }, [clearCache]);

  return {
    makeRequest,
    cancelRequest,
    clearCache
  };
}

// Hook for memory usage monitoring
export function useMemoryMonitoring(interval: number = 10000) {
  const [memoryUsage, setMemoryUsage] = useState<number | null>(null);

  useEffect(() => {
    const updateMemoryUsage = () => {
      const usage = performanceService.getMemoryUsage();
      setMemoryUsage(usage);
      
      if (usage && usage > 50 * 1024 * 1024) { // 50MB threshold
        console.warn(`High memory usage detected: ${(usage / 1024 / 1024).toFixed(2)}MB`);
      }
    };

    updateMemoryUsage();
    const intervalId = setInterval(updateMemoryUsage, interval);

    return () => clearInterval(intervalId);
  }, [interval]);

  return memoryUsage;
}

// Hook for efficient list rendering with windowing
export function useWindowedList<T>(
  items: T[],
  itemHeight: number,
  containerHeight: number,
  buffer: number = 5
) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - buffer);
  const endIndex = Math.min(
    items.length - 1,
    Math.floor((scrollTop + containerHeight) / itemHeight) + buffer
  );

  const visibleItems = useMemo(() => {
    return items.slice(startIndex, endIndex + 1).map((item, index) => ({
      item,
      index: startIndex + index,
      style: {
        position: 'absolute' as const,
        top: (startIndex + index) * itemHeight,
        height: itemHeight,
        left: 0,
        right: 0
      }
    }));
  }, [items, startIndex, endIndex, itemHeight]);

  const handleScroll = useThrottle((event: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  }, 16);

  return {
    containerRef,
    visibleItems,
    totalHeight: items.length * itemHeight,
    handleScroll,
    startIndex,
    endIndex
  };
}

// Hook for batch updates
export function useBatchUpdates<T>(
  batchSize: number = 10,
  delay: number = 100
) {
  const [items, setItems] = useState<T[]>([]);
  const batchRef = useRef<T[]>([]);
  const timeoutRef = useRef<NodeJS.Timeout>();

  const addItem = useCallback((item: T) => {
    batchRef.current.push(item);

    if (batchRef.current.length >= batchSize) {
      // Flush immediately if batch is full
      setItems(prev => [...prev, ...batchRef.current]);
      batchRef.current = [];
      
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = undefined;
      }
    } else {
      // Set timeout to flush remaining items
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      
      timeoutRef.current = setTimeout(() => {
        if (batchRef.current.length > 0) {
          setItems(prev => [...prev, ...batchRef.current]);
          batchRef.current = [];
        }
        timeoutRef.current = undefined;
      }, delay);
    }
  }, [batchSize, delay]);

  const clearItems = useCallback(() => {
    setItems([]);
    batchRef.current = [];
    
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = undefined;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return {
    items,
    addItem,
    clearItems,
    pendingCount: batchRef.current.length
  };
}