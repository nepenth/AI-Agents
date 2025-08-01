/* ===== PERFORMANCE & ACCESSIBILITY TESTING FRAMEWORK ===== */

class PerformanceAccessibilityTester {
    constructor() {
        this.performanceResults = [];
        this.accessibilityResults = [];
        this.frameRateMonitor = null;
        this.isMonitoring = false;
        
        this.init();
    }
    
    init() {
        this.setupPerformanceObserver();
        console.log('⚡ Performance & Accessibility Tester initialized');
    }
    
    setupPerformanceObserver() {
        if ('PerformanceObserver' in window) {
            // Monitor paint timing
            const paintObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.performanceResults.push({
                        type: 'paint',
                        name: entry.name,
                        startTime: entry.startTime,
                        timestamp: Date.now()
                    });
                }
            });
            paintObserver.observe({ entryTypes: ['paint'] });
            
            // Monitor layout shifts
            const layoutShiftObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    if (!entry.hadRecentInput) {
                        this.performanceResults.push({
                            type: 'layout-shift',
                            value: entry.value,
                            startTime: entry.startTime,
                            timestamp: Date.now()
                        });
                    }
                }
            });
            layoutShiftObserver.observe({ entryTypes: ['layout-shift'] });
            
            // Monitor long tasks
            const longTaskObserver = new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                    this.performanceResults.push({
                        type: 'long-task',
                        duration: entry.duration,
                        startTime: entry.startTime,
                        timestamp: Date.now()
                    });
                }
            });
            longTaskObserver.observe({ entryTypes: ['longtask'] });
        }
    }
    
    // Frame Rate Testing
    startFrameRateMonitoring() {
        if (this.isMonitoring) return;
        
        this.isMonitoring = true;
        this.frameRateData = [];
        let lastTime = performance.now();
        let frameCount = 0;
        
        const measureFrameRate = (currentTime) => {
            frameCount++;
            
            if (currentTime - lastTime >= 1000) {
                const fps = Math.round((frameCount * 1000) / (currentTime - lastTime));
                this.frameRateData.push({
                    fps: fps,
                    timestamp: currentTime
                });
                
                frameCount = 0;
                lastTime = currentTime;
            }
            
            if (this.isMonitoring) {
                this.frameRateMonitor = requestAnimationFrame(measureFrameRate);
            }
        };
        
        this.frameRateMonitor = requestAnimationFrame(measureFrameRate);
        console.log('📊 Frame rate monitoring started');
    }
    
    stopFrameRateMonitoring() {
        this.isMonitoring = false;
        if (this.frameRateMonitor) {
            cancelAnimationFrame(this.frameRateMonitor);
        }
        
        const avgFps = this.frameRateData.reduce((sum, data) => sum + data.fps, 0) / this.frameRateData.length;
        const minFps = Math.min(...this.frameRateData.map(d => d.fps));
        const maxFps = Math.max(...this.frameRateData.map(d => d.fps));
        
        const result = {
            average: Math.round(avgFps),
            minimum: minFps,
            maximum: maxFps,
            samples: this.frameRateData.length,
            data: this.frameRateData
        };
        
        console.log('📊 Frame rate monitoring stopped:', result);
        return result;
    }
    
    // Animation Performance Testing
    async testAnimationPerformance() {
        console.log('🎬 Testing animation performance...');
        
        const animations = [
            { name: 'glass-slide-in', class: 'animate-glass-slide-in' },
            { name: 'glass-fade-in', class: 'animate-glass-fade-in' },
            { name: 'lift-hover', class: 'animate-lift-hover' },
            { name: 'shimmer', class: 'animate-shimmer-strong' }
        ];
        
        const results = [];
        
        for (const animation of animations) {
            const result = await this.testSingleAnimation(animation);
            results.push(result);
        }
        
        return results;
    }
    
    async testSingleAnimation(animation) {
        return new Promise((resolve) => {
            // Create test element
            const testElement = document.createElement('div');
            testElement.className = 'glass-panel-v3';
            testElement.style.cssText = `
                position: fixed;
                top: -200px;
                left: -200px;
                width: 100px;
                height: 100px;
                z-index: -1;
            `;
            document.body.appendChild(testElement);
            
            // Start monitoring
            this.startFrameRateMonitoring();
            const startTime = performance.now();
            
            // Trigger animation
            testElement.classList.add(animation.class);
            
            // Wait for animation to complete
            setTimeout(() => {
                const endTime = performance.now();
                const frameRateResult = this.stopFrameRateMonitoring();
                
                // Clean up
                document.body.removeChild(testElement);
                
                resolve({
                    animation: animation.name,
                    duration: endTime - startTime,
                    frameRate: frameRateResult,
                    performance: frameRateResult.average >= 55 ? 'good' : 
                                frameRateResult.average >= 30 ? 'acceptable' : 'poor'
                });
            }, 1000);
        });
    }
    
    // Glass Effect Performance Testing
    testGlassEffectPerformance() {
        console.log('🔍 Testing glass effect performance...');
        
        const testElement = document.createElement('div');
        testElement.className = 'glass-panel-v3';
        testElement.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            width: 300px;
            height: 200px;
            transform: translate(-50%, -50%);
            z-index: 9999;
        `;
        
        document.body.appendChild(testElement);
        
        // Test backdrop-filter performance
        const startTime = performance.now();
        this.startFrameRateMonitoring();
        
        // Simulate interaction
        testElement.addEventListener('mouseenter', () => {
            testElement.style.backdropFilter = 'blur(20px) saturate(200%)';
        });
        
        testElement.addEventListener('mouseleave', () => {
            testElement.style.backdropFilter = 'blur(10px) saturate(180%)';
        });
        
        // Trigger hover states
        testElement.dispatchEvent(new MouseEvent('mouseenter'));
        
        setTimeout(() => {
            testElement.dispatchEvent(new MouseEvent('mouseleave'));
            
            setTimeout(() => {
                const endTime = performance.now();
                const frameRateResult = this.stopFrameRateMonitoring();
                
                document.body.removeChild(testElement);
                
                const result = {
                    test: 'glass-effect-performance',
                    duration: endTime - startTime,
                    frameRate: frameRateResult,
                    performance: frameRateResult.average >= 55 ? 'excellent' : 
                                frameRateResult.average >= 45 ? 'good' : 
                                frameRateResult.average >= 30 ? 'acceptable' : 'poor'
                };
                
                console.log('🔍 Glass effect performance result:', result);
                return result;
            }, 500);
        }, 500);
    }
    
    // Accessibility Testing
    async runAccessibilityAudit() {
        console.log('♿ Running accessibility audit...');
        
        const results = {
            colorContrast: await this.testColorContrast(),
            keyboardNavigation: await this.testKeyboardNavigation(),
            ariaLabels: await this.testAriaLabels(),
            focusManagement: await this.testFocusManagement(),
            semanticStructure: await this.testSemanticStructure(),
            reducedMotion: await this.testReducedMotionSupport()
        };
        
        this.accessibilityResults = results;
        return results;
    }
    
    async testColorContrast() {
        const elements = document.querySelectorAll('*');
        const contrastIssues = [];
        
        for (const element of elements) {
            const styles = window.getComputedStyle(element);
            const textColor = styles.color;
            const backgroundColor = styles.backgroundColor;
            
            if (textColor && backgroundColor && backgroundColor !== 'rgba(0, 0, 0, 0)') {
                const contrast = this.calculateContrastRatio(textColor, backgroundColor);
                
                if (contrast < 4.5) { // WCAG AA standard
                    contrastIssues.push({
                        element: element.tagName.toLowerCase(),
                        class: element.className,
                        textColor: textColor,
                        backgroundColor: backgroundColor,
                        contrast: contrast.toFixed(2),
                        wcagLevel: contrast >= 3 ? 'AA Large' : 'Fail'
                    });
                }
            }
        }
        
        return {
            passed: contrastIssues.length === 0,
            issues: contrastIssues,
            summary: `${contrastIssues.length} contrast issues found`
        };
    }
    
    calculateContrastRatio(color1, color2) {
        // Simplified contrast calculation
        // In production, use a proper color contrast library
        const rgb1 = this.parseColor(color1);
        const rgb2 = this.parseColor(color2);
        
        const l1 = this.getLuminance(rgb1);
        const l2 = this.getLuminance(rgb2);
        
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        
        return (lighter + 0.05) / (darker + 0.05);
    }
    
    parseColor(color) {
        // Simple RGB extraction - enhance for production
        const match = color.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
        if (match) {
            return {
                r: parseInt(match[1]),
                g: parseInt(match[2]),
                b: parseInt(match[3])
            };
        }
        return { r: 0, g: 0, b: 0 };
    }
    
    getLuminance(rgb) {
        const { r, g, b } = rgb;
        const [rs, gs, bs] = [r, g, b].map(c => {
            c = c / 255;
            return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
    }
    
    async testKeyboardNavigation() {
        const focusableElements = document.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])'
        );
        
        const issues = [];
        
        for (const element of focusableElements) {
            // Test if element is focusable
            element.focus();
            if (document.activeElement !== element) {
                issues.push({
                    element: element.tagName.toLowerCase(),
                    class: element.className,
                    issue: 'Element not focusable'
                });
            }
            
            // Test if element has visible focus indicator
            const styles = window.getComputedStyle(element, ':focus');
            if (!styles.outline || styles.outline === 'none') {
                issues.push({
                    element: element.tagName.toLowerCase(),
                    class: element.className,
                    issue: 'No visible focus indicator'
                });
            }
        }
        
        return {
            passed: issues.length === 0,
            focusableElements: focusableElements.length,
            issues: issues,
            summary: `${issues.length} keyboard navigation issues found`
        };
    }
    
    async testAriaLabels() {
        const elementsNeedingLabels = document.querySelectorAll(
            'button:not([aria-label]):not([aria-labelledby]), ' +
            'input:not([aria-label]):not([aria-labelledby]):not([id]), ' +
            '[role=\"button\"]:not([aria-label]):not([aria-labelledby])'
        );
        
        const issues = [];
        
        for (const element of elementsNeedingLabels) {
            if (!element.textContent.trim() && !element.title) {
                issues.push({
                    element: element.tagName.toLowerCase(),
                    class: element.className,
                    issue: 'Missing accessible label'
                });
            }
        }
        
        return {
            passed: issues.length === 0,
            issues: issues,
            summary: `${issues.length} ARIA label issues found`
        };
    }
    
    async testFocusManagement() {
        const modals = document.querySelectorAll('[role=\"dialog\"], .modal');
        const issues = [];
        
        for (const modal of modals) {
            // Test if modal traps focus
            const focusableInModal = modal.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex=\"-1\"])'
            );
            
            if (focusableInModal.length === 0) {
                issues.push({
                    element: 'modal',
                    class: modal.className,
                    issue: 'Modal has no focusable elements'
                });
            }
        }
        
        return {
            passed: issues.length === 0,
            issues: issues,
            summary: `${issues.length} focus management issues found`
        };
    }
    
    async testSemanticStructure() {
        const issues = [];
        
        // Test heading hierarchy
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        let lastLevel = 0;
        
        for (const heading of headings) {
            const level = parseInt(heading.tagName.charAt(1));
            if (level > lastLevel + 1) {
                issues.push({
                    element: heading.tagName.toLowerCase(),
                    issue: `Heading level skipped (${lastLevel} to ${level})`
                });
            }
            lastLevel = level;
        }
        
        // Test landmark roles
        const landmarks = document.querySelectorAll('main, nav, aside, header, footer, [role=\"main\"], [role=\"navigation\"], [role=\"complementary\"]');
        if (landmarks.length === 0) {
            issues.push({
                element: 'page',
                issue: 'No landmark roles found'
            });
        }
        
        return {
            passed: issues.length === 0,
            issues: issues,
            summary: `${issues.length} semantic structure issues found`
        };
    }
    
    async testReducedMotionSupport() {
        const animatedElements = document.querySelectorAll('[class*=\"animate-\"]');
        const issues = [];
        
        // Test if reduced motion is respected
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        
        if (prefersReducedMotion) {
            for (const element of animatedElements) {
                const styles = window.getComputedStyle(element);
                if (styles.animationDuration !== '0s' && styles.animationDuration !== 'none') {
                    issues.push({
                        element: element.tagName.toLowerCase(),
                        class: element.className,
                        issue: 'Animation not disabled for reduced motion preference'
                    });
                }
            }
        }
        
        return {
            passed: issues.length === 0,
            prefersReducedMotion: prefersReducedMotion,
            animatedElements: animatedElements.length,
            issues: issues,
            summary: `${issues.length} reduced motion issues found`
        };
    }
    
    // Generate comprehensive report
    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            performance: {
                frameRate: this.frameRateData || [],
                glassEffects: this.performanceResults.filter(r => r.type === 'glass-effect'),
                animations: this.performanceResults.filter(r => r.type === 'animation'),
                layoutShifts: this.performanceResults.filter(r => r.type === 'layout-shift'),
                longTasks: this.performanceResults.filter(r => r.type === 'long-task')
            },
            accessibility: this.accessibilityResults,
            summary: this.generateSummary()
        };
        
        console.log('📋 Performance & Accessibility Report:', report);
        return report;
    }
    
    generateSummary() {
        const performanceScore = this.calculatePerformanceScore();
        const accessibilityScore = this.calculateAccessibilityScore();
        
        return {
            performanceScore: performanceScore,
            accessibilityScore: accessibilityScore,
            overallScore: Math.round((performanceScore + accessibilityScore) / 2),
            recommendations: this.generateRecommendations(performanceScore, accessibilityScore)
        };
    }
    
    calculatePerformanceScore() {
        // Simple scoring based on frame rate and issues
        const avgFps = this.frameRateData ? 
            this.frameRateData.reduce((sum, data) => sum + data.fps, 0) / this.frameRateData.length : 60;
        
        const layoutShifts = this.performanceResults.filter(r => r.type === 'layout-shift').length;
        const longTasks = this.performanceResults.filter(r => r.type === 'long-task').length;
        
        let score = 100;
        score -= Math.max(0, (60 - avgFps) * 2); // Deduct for low FPS
        score -= layoutShifts * 5; // Deduct for layout shifts
        score -= longTasks * 10; // Deduct for long tasks
        
        return Math.max(0, Math.round(score));
    }
    
    calculateAccessibilityScore() {
        if (!this.accessibilityResults) return 100;
        
        let score = 100;
        Object.values(this.accessibilityResults).forEach(result => {
            if (result.issues) {
                score -= result.issues.length * 5;
            }
        });
        
        return Math.max(0, Math.round(score));
    }
    
    generateRecommendations(performanceScore, accessibilityScore) {
        const recommendations = [];
        
        if (performanceScore < 80) {
            recommendations.push('Consider optimizing animations and reducing glass effect complexity');
            recommendations.push('Monitor and reduce layout shifts');
            recommendations.push('Break up long-running JavaScript tasks');
        }
        
        if (accessibilityScore < 80) {
            recommendations.push('Improve color contrast ratios');
            recommendations.push('Add missing ARIA labels and descriptions');
            recommendations.push('Ensure all interactive elements are keyboard accessible');
            recommendations.push('Implement proper focus management');
        }
        
        return recommendations;
    }
    
    exportReport() {
        const report = this.generateReport();
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `performance-accessibility-report-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Initialize testing framework
window.PerformanceAccessibilityTester = PerformanceAccessibilityTester;

// Auto-initialize in development mode
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.pat = new PerformanceAccessibilityTester();
    
    console.log('⚡ Performance & Accessibility Testing available:');
    console.log('- pat.testAnimationPerformance() - Test animation frame rates');
    console.log('- pat.testGlassEffectPerformance() - Test glass effect performance');
    console.log('- pat.runAccessibilityAudit() - Run full accessibility audit');
    console.log('- pat.generateReport() - Generate comprehensive report');
    console.log('- pat.exportReport() - Export test results');
}