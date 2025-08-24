import { config } from '@/config';

export interface PerformanceMetrics {
  // Core Web Vitals
  lcp?: number; // Largest Contentful Paint
  fid?: number; // First Input Delay
  cls?: number; // Cumulative Layout Shift
  fcp?: number; // First Contentful Paint
  ttfb?: number; // Time to First Byte
  
  // Custom metrics
  componentRenderTime?: number;
  apiResponseTime?: number;
  websocketLatency?: number;
  memoryUsage?: number;
  
  // User interaction metrics
  pageLoadTime?: number;
  routeChangeTime?: number;
  searchResponseTime?: number;
  
  // Error metrics
  errorRate?: number;
  crashRate?: number;
  
  timestamp: number;
  url: string;
  userAgent: string;
}

export interface PerformanceBudget {
  lcp: number; // 2.5s
  fid: number; // 100ms
  cls: number; // 0.1
  fcp: number; // 1.8s
  ttfb: number; // 600ms
  apiResponseTime: number; // 1000ms
  websocketLatency: number; // 100ms
}

class PerformanceService {
  private metrics: PerformanceMetrics[] = [];
  private budget: PerformanceBudget = {
    lcp: 2500,
    fid: 100,
    cls: 0.1,
    fcp: 1800,
    ttfb: 600,
    apiResponseTime: 1000,
    websocketLatency: 100
  };
  private observer: PerformanceObserver | null = null;
  private isMonitoring = false;

  constructor() {
    this.initializePerformanceObserver();
    this.setupWebVitals();
  }

  private initializePerformanceObserver() {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) {
      return;
    }

    try {
      this.observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.processPerformanceEntry(entry);
        }
      });

      // Observe different types of performance entries
      this.observer.observe({ entryTypes: ['navigation', 'resource', 'measure', 'paint'] });
    } catch (error) {
      console.warn('Performance Observer not supported:', error);
    }
  }

  private setupWebVitals() {
    if (typeof window === 'undefined') return;

    // Largest Contentful Paint
    this.observeWebVital('largest-contentful-paint', (entry: any) => {
      this.recordMetric({ lcp: entry.value });
    });

    // First Input Delay
    this.observeWebVital('first-input', (entry: any) => {
      this.recordMetric({ fid: entry.processingStart - entry.startTime });
    });

    // Cumulative Layout Shift
    this.observeWebVital('layout-shift', (entry: any) => {
      if (!entry.hadRecentInput) {
        this.recordMetric({ cls: entry.value });
      }
    });

    // First Contentful Paint
    if (performance.getEntriesByType) {
      const paintEntries = performance.getEntriesByType('paint');
      const fcpEntry = paintEntries.find(entry => entry.name === 'first-contentful-paint');
      if (fcpEntry) {
        this.recordMetric({ fcp: fcpEntry.startTime });
      }
    }
  }

  private observeWebVital(type: string, callback: (entry: any) => void) {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          callback(entry);
        }
      });
      observer.observe({ type, buffered: true });
    } catch (error) {
      console.warn(`Failed to observe ${type}:`, error);
    }
  }

  private processPerformanceEntry(entry: PerformanceEntry) {
    if (entry.entryType === 'navigation') {
      const navEntry = entry as PerformanceNavigationTiming;
      this.recordMetric({
        ttfb: navEntry.responseStart - navEntry.requestStart,
        pageLoadTime: navEntry.loadEventEnd - navEntry.navigationStart
      });
    } else if (entry.entryType === 'resource') {
      const resourceEntry = entry as PerformanceResourceTiming;
      if (resourceEntry.name.includes('/api/')) {
        this.recordMetric({
          apiResponseTime: resourceEntry.responseEnd - resourceEntry.requestStart
        });
      }
    }
  }

  private recordMetric(metrics: Partial<PerformanceMetrics>) {
    const fullMetrics: PerformanceMetrics = {
      ...metrics,
      timestamp: Date.now(),
      url: window.location.href,
      userAgent: navigator.userAgent
    };

    this.metrics.push(fullMetrics);

    // Keep only last 100 metrics to prevent memory issues
    if (this.metrics.length > 100) {
      this.metrics = this.metrics.slice(-100);
    }

    // Check against performance budget
    this.checkPerformanceBudget(fullMetrics);

    // Send to analytics if configured
    if (config.analyticsEnabled) {
      this.sendToAnalytics(fullMetrics);
    }
  }

  private checkPerformanceBudget(metrics: PerformanceMetrics) {
    const violations: string[] = [];

    if (metrics.lcp && metrics.lcp > this.budget.lcp) {
      violations.push(`LCP: ${metrics.lcp}ms > ${this.budget.lcp}ms`);
    }
    if (metrics.fid && metrics.fid > this.budget.fid) {
      violations.push(`FID: ${metrics.fid}ms > ${this.budget.fid}ms`);
    }
    if (metrics.cls && metrics.cls > this.budget.cls) {
      violations.push(`CLS: ${metrics.cls} > ${this.budget.cls}`);
    }
    if (metrics.fcp && metrics.fcp > this.budget.fcp) {
      violations.push(`FCP: ${metrics.fcp}ms > ${this.budget.fcp}ms`);
    }
    if (metrics.ttfb && metrics.ttfb > this.budget.ttfb) {
      violations.push(`TTFB: ${metrics.ttfb}ms > ${this.budget.ttfb}ms`);
    }
    if (metrics.apiResponseTime && metrics.apiResponseTime > this.budget.apiResponseTime) {
      violations.push(`API Response: ${metrics.apiResponseTime}ms > ${this.budget.apiResponseTime}ms`);
    }

    if (violations.length > 0) {
      console.warn('Performance budget violations:', violations);
      
      // Emit performance warning event
      window.dispatchEvent(new CustomEvent('performance-warning', {
        detail: { violations, metrics }
      }));
    }
  }

  private async sendToAnalytics(metrics: PerformanceMetrics) {
    try {
      // Send to your analytics service
      await fetch('/api/v1/analytics/performance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(metrics)
      });
    } catch (error) {
      console.warn('Failed to send performance metrics:', error);
    }
  }

  // Public API
  startMonitoring() {
    this.isMonitoring = true;
    console.log('Performance monitoring started');
  }

  stopMonitoring() {
    this.isMonitoring = false;
    if (this.observer) {
      this.observer.disconnect();
    }
    console.log('Performance monitoring stopped');
  }

  getMetrics(): PerformanceMetrics[] {
    return [...this.metrics];
  }

  getLatestMetrics(): PerformanceMetrics | null {
    return this.metrics.length > 0 ? this.metrics[this.metrics.length - 1] : null;
  }

  getAverageMetrics(): Partial<PerformanceMetrics> {
    if (this.metrics.length === 0) return {};

    const totals = this.metrics.reduce((acc, metric) => {
      Object.keys(metric).forEach(key => {
        if (typeof metric[key as keyof PerformanceMetrics] === 'number') {
          acc[key] = (acc[key] || 0) + (metric[key as keyof PerformanceMetrics] as number);
        }
      });
      return acc;
    }, {} as Record<string, number>);

    const averages: Partial<PerformanceMetrics> = {};
    Object.keys(totals).forEach(key => {
      averages[key as keyof PerformanceMetrics] = totals[key] / this.metrics.length;
    });

    return averages;
  }

  measureComponentRender<T>(componentName: string, renderFn: () => T): T {
    const startTime = performance.now();
    const result = renderFn();
    const endTime = performance.now();
    
    this.recordMetric({
      componentRenderTime: endTime - startTime
    });

    if (endTime - startTime > 16) { // More than one frame (60fps)
      console.warn(`Slow component render: ${componentName} took ${endTime - startTime}ms`);
    }

    return result;
  }

  measureApiCall<T>(apiName: string, apiCall: () => Promise<T>): Promise<T> {
    const startTime = performance.now();
    
    return apiCall().then(result => {
      const endTime = performance.now();
      this.recordMetric({
        apiResponseTime: endTime - startTime
      });
      return result;
    }).catch(error => {
      const endTime = performance.now();
      this.recordMetric({
        apiResponseTime: endTime - startTime,
        errorRate: 1
      });
      throw error;
    });
  }

  measureWebSocketLatency() {
    const startTime = performance.now();
    
    // Send ping and measure response time
    const { websocketService } = require('./websocket');
    
    const unsubscribe = websocketService.subscribe('pong', () => {
      const endTime = performance.now();
      this.recordMetric({
        websocketLatency: endTime - startTime
      });
      unsubscribe();
    });

    websocketService.send('ping', { timestamp: startTime });
  }

  getMemoryUsage(): number | null {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      return memory.usedJSHeapSize;
    }
    return null;
  }

  recordMemoryUsage() {
    const memoryUsage = this.getMemoryUsage();
    if (memoryUsage) {
      this.recordMetric({ memoryUsage });
    }
  }

  setBudget(budget: Partial<PerformanceBudget>) {
    this.budget = { ...this.budget, ...budget };
  }

  getBudget(): PerformanceBudget {
    return { ...this.budget };
  }

  clearMetrics() {
    this.metrics = [];
  }

  // Performance optimization helpers
  debounce<T extends (...args: any[]) => any>(func: T, wait: number): T {
    let timeout: NodeJS.Timeout;
    return ((...args: any[]) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    }) as T;
  }

  throttle<T extends (...args: any[]) => any>(func: T, limit: number): T {
    let inThrottle: boolean;
    return ((...args: any[]) => {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    }) as T;
  }

  // Lazy loading helper
  createIntersectionObserver(callback: (entries: IntersectionObserverEntry[]) => void, options?: IntersectionObserverInit) {
    if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
      return null;
    }

    return new IntersectionObserver(callback, {
      rootMargin: '50px',
      threshold: 0.1,
      ...options
    });
  }
}

export const performanceService = new PerformanceService();

// React hook for performance monitoring
export function usePerformanceMonitoring() {
  const [metrics, setMetrics] = React.useState<PerformanceMetrics[]>([]);
  const [isMonitoring, setIsMonitoring] = React.useState(false);

  React.useEffect(() => {
    const updateMetrics = () => {
      setMetrics(performanceService.getMetrics());
    };

    // Update metrics every 5 seconds
    const interval = setInterval(updateMetrics, 5000);
    updateMetrics(); // Initial update

    return () => clearInterval(interval);
  }, []);

  const startMonitoring = React.useCallback(() => {
    performanceService.startMonitoring();
    setIsMonitoring(true);
  }, []);

  const stopMonitoring = React.useCallback(() => {
    performanceService.stopMonitoring();
    setIsMonitoring(false);
  }, []);

  return {
    metrics,
    isMonitoring,
    startMonitoring,
    stopMonitoring,
    latestMetrics: performanceService.getLatestMetrics(),
    averageMetrics: performanceService.getAverageMetrics(),
    budget: performanceService.getBudget(),
    setBudget: performanceService.setBudget.bind(performanceService)
  };
}