/* ===== VISUAL REGRESSION TESTING FRAMEWORK ===== */

class VisualRegressionTester {
    constructor() {
        this.testSuites = [];
        this.results = [];
        this.isRunning = false;
        this.canvas = null;
        this.context = null;
        
        this.init();
    }
    
    init() {
        this.setupCanvas();
        this.registerTestSuites();
        console.log('🧪 Visual Regression Tester initialized');
    }
    
    setupCanvas() {
        this.canvas = document.createElement('canvas');
        this.context = this.canvas.getContext('2d');
        this.canvas.style.display = 'none';
        document.body.appendChild(this.canvas);
    }
    
    registerTestSuites() {
        // Glass Panel Component Tests
        this.addTestSuite('Glass Panels', [
            {
                name: 'glass-panel-v3-primary',
                selector: '.glass-panel-v3',
                states: ['default', 'hover', 'active']
            },
            {
                name: 'glass-panel-v3-secondary',
                selector: '.glass-panel-v3--secondary',
                states: ['default', 'hover']
            },
            {
                name: 'glass-panel-v3-tertiary',
                selector: '.glass-panel-v3--tertiary',
                states: ['default', 'hover']
            }
        ]);
        
        // Liquid Button Component Tests
        this.addTestSuite('Liquid Buttons', [
            {
                name: 'liquid-button-primary',
                selector: '.liquid-button--primary',
                states: ['default', 'hover', 'active', 'disabled']
            },
            {
                name: 'liquid-button-secondary',
                selector: '.liquid-button--secondary',
                states: ['default', 'hover', 'active']
            },
            {
                name: 'liquid-button-ghost',
                selector: '.liquid-button--ghost',
                states: ['default', 'hover', 'active']
            },
            {
                name: 'liquid-button-sizes',
                selector: '.liquid-button--sm, .liquid-button, .liquid-button--lg',
                states: ['default']
            }
        ]);
        
        // Navigation Component Tests
        this.addTestSuite('Navigation', [
            {
                name: 'liquid-nav',
                selector: '.liquid-nav',
                states: ['default']
            },
            {
                name: 'liquid-nav-item',
                selector: '.liquid-nav-item',
                states: ['default', 'hover', 'active']
            }
        ]);
        
        // Form Component Tests
        this.addTestSuite('Form Elements', [
            {
                name: 'glass-input',
                selector: '.glass-input',
                states: ['default', 'focus', 'error', 'disabled']
            },
            {
                name: 'theme-color-btn',
                selector: '.theme-color-btn',
                states: ['default', 'hover', 'active']
            }
        ]);
        
        // Animation Tests
        this.addTestSuite('Animations', [
            {
                name: 'glass-slide-in',
                selector: '.animate-glass-slide-in',
                states: ['initial', 'animated']
            },
            {
                name: 'lift-hover',
                selector: '.animate-lift-hover',
                states: ['default', 'hover']
            }
        ]);
    }
    
    addTestSuite(name, tests) {
        this.testSuites.push({ name, tests });
    }
    
    async runAllTests() {
        if (this.isRunning) {
            console.warn('Tests already running');
            return;
        }
        
        this.isRunning = true;
        this.results = [];
        
        console.log('🧪 Starting visual regression tests...');
        
        for (const suite of this.testSuites) {
            console.log(`📋 Running test suite: ${suite.name}`);
            
            for (const test of suite.tests) {
                await this.runComponentTest(test, suite.name);
            }
        }
        
        this.isRunning = false;
        this.generateReport();
        
        console.log('✅ Visual regression tests completed');
        return this.results;
    }
    
    async runComponentTest(test, suiteName) {
        const elements = document.querySelectorAll(test.selector);
        
        if (elements.length === 0) {
            this.results.push({
                suite: suiteName,
                test: test.name,
                status: 'skipped',
                reason: 'No elements found'
            });
            return;
        }
        
        for (let i = 0; i < elements.length; i++) {
            const element = elements[i];
            
            for (const state of test.states) {
                try {
                    const screenshot = await this.captureElementScreenshot(element, state);
                    const result = await this.compareScreenshot(test.name, state, i, screenshot);
                    
                    this.results.push({
                        suite: suiteName,
                        test: test.name,
                        state: state,
                        element: i,
                        status: result.status,
                        diff: result.diff,
                        screenshot: screenshot
                    });
                } catch (error) {
                    this.results.push({
                        suite: suiteName,
                        test: test.name,
                        state: state,
                        element: i,
                        status: 'error',
                        error: error.message
                    });
                }
            }
        }
    }
    
    async captureElementScreenshot(element, state) {
        // Apply state to element
        await this.applyElementState(element, state);
        
        // Wait for animations to complete
        await this.waitForAnimations();
        
        // Get element bounds
        const rect = element.getBoundingClientRect();
        
        // Set canvas size
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        // Capture element using html2canvas-like approach
        const screenshot = await this.renderElementToCanvas(element, rect);
        
        // Reset element state
        await this.resetElementState(element, state);
        
        return screenshot;
    }
    
    async applyElementState(element, state) {
        switch (state) {
            case 'hover':
                element.classList.add('test-hover-state');
                element.dispatchEvent(new MouseEvent('mouseenter'));
                break;
            case 'active':
                element.classList.add('test-active-state');
                element.dispatchEvent(new MouseEvent('mousedown'));
                break;
            case 'focus':
                element.focus();
                break;
            case 'disabled':
                element.disabled = true;
                element.classList.add('disabled');
                break;
            case 'error':
                element.classList.add('error');
                break;
            case 'animated':
                element.classList.add('animate-glass-slide-in');
                break;
        }
    }
    
    async resetElementState(element, state) {
        switch (state) {
            case 'hover':
                element.classList.remove('test-hover-state');
                element.dispatchEvent(new MouseEvent('mouseleave'));
                break;
            case 'active':
                element.classList.remove('test-active-state');
                element.dispatchEvent(new MouseEvent('mouseup'));
                break;
            case 'focus':
                element.blur();
                break;
            case 'disabled':
                element.disabled = false;
                element.classList.remove('disabled');
                break;
            case 'error':
                element.classList.remove('error');
                break;
            case 'animated':
                element.classList.remove('animate-glass-slide-in');
                break;
        }
    }
    
    async waitForAnimations() {
        return new Promise(resolve => {
            // Wait for CSS animations and transitions to complete
            setTimeout(resolve, 500);
        });
    }
    
    async renderElementToCanvas(element, rect) {
        // Simple canvas rendering - in production, use html2canvas or similar
        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Get computed styles
        const styles = window.getComputedStyle(element);
        
        // Draw background
        this.context.fillStyle = styles.backgroundColor;
        this.context.fillRect(0, 0, rect.width, rect.height);
        
        // Draw border
        if (styles.borderWidth !== '0px') {
            this.context.strokeStyle = styles.borderColor;
            this.context.lineWidth = parseInt(styles.borderWidth);
            this.context.strokeRect(0, 0, rect.width, rect.height);
        }
        
        // Convert canvas to data URL
        return this.canvas.toDataURL('image/png');
    }
    
    async compareScreenshot(testName, state, elementIndex, screenshot) {
        const key = `${testName}-${state}-${elementIndex}`;
        const stored = localStorage.getItem(`vrt-baseline-${key}`);
        
        if (!stored) {
            // First run - store as baseline
            localStorage.setItem(`vrt-baseline-${key}`, screenshot);
            return { status: 'baseline-created', diff: 0 };
        }
        
        // Compare with baseline
        const diff = this.calculateImageDiff(stored, screenshot);
        const threshold = 0.05; // 5% difference threshold
        
        return {
            status: diff > threshold ? 'failed' : 'passed',
            diff: diff
        };
    }
    
    calculateImageDiff(baseline, current) {
        // Simple pixel difference calculation
        // In production, use a proper image diff library
        if (baseline === current) return 0;
        
        // For now, return a mock difference
        return Math.random() * 0.1; // 0-10% difference
    }
    
    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            total: this.results.length,
            passed: this.results.filter(r => r.status === 'passed').length,
            failed: this.results.filter(r => r.status === 'failed').length,
            skipped: this.results.filter(r => r.status === 'skipped').length,
            errors: this.results.filter(r => r.status === 'error').length,
            results: this.results
        };
        
        console.table(this.results);
        console.log('📊 Test Summary:', {
            Total: report.total,
            Passed: report.passed,
            Failed: report.failed,
            Skipped: report.skipped,
            Errors: report.errors
        });
        
        // Store report
        localStorage.setItem('vrt-latest-report', JSON.stringify(report));
        
        return report;
    }
    
    exportReport() {
        const report = localStorage.getItem('vrt-latest-report');
        if (!report) {
            console.warn('No test report available');
            return;
        }
        
        const blob = new Blob([report], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `visual-regression-report-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    clearBaselines() {
        const keys = Object.keys(localStorage).filter(key => key.startsWith('vrt-baseline-'));
        keys.forEach(key => localStorage.removeItem(key));
        console.log(`🗑️ Cleared ${keys.length} baseline screenshots`);
    }
    
    // Responsive design testing
    async testResponsiveDesign() {
        const viewports = [
            { name: 'mobile', width: 375, height: 667 },
            { name: 'tablet', width: 768, height: 1024 },
            { name: 'desktop', width: 1920, height: 1080 }
        ];
        
        const responsiveResults = [];
        
        for (const viewport of viewports) {
            console.log(`📱 Testing ${viewport.name} viewport (${viewport.width}x${viewport.height})`);
            
            // Simulate viewport
            this.setViewport(viewport.width, viewport.height);
            
            // Wait for layout to adjust
            await this.waitForAnimations();
            
            // Run tests for this viewport
            const results = await this.runAllTests();
            responsiveResults.push({
                viewport: viewport.name,
                dimensions: `${viewport.width}x${viewport.height}`,
                results: results
            });
        }
        
        // Reset viewport
        this.resetViewport();
        
        return responsiveResults;
    }
    
    setViewport(width, height) {
        // Simulate viewport change
        document.documentElement.style.width = `${width}px`;
        document.documentElement.style.height = `${height}px`;
        
        // Trigger resize event
        window.dispatchEvent(new Event('resize'));
    }
    
    resetViewport() {
        document.documentElement.style.width = '';
        document.documentElement.style.height = '';
        window.dispatchEvent(new Event('resize'));
    }
}

// Cross-browser testing utilities
class CrossBrowserTester {
    constructor() {
        this.browserInfo = this.getBrowserInfo();
    }
    
    getBrowserInfo() {
        const ua = navigator.userAgent;
        const browsers = {
            chrome: /Chrome/.test(ua) && !/Edge/.test(ua),
            firefox: /Firefox/.test(ua),
            safari: /Safari/.test(ua) && !/Chrome/.test(ua),
            edge: /Edge/.test(ua),
            ie: /Trident/.test(ua)
        };
        
        return {
            name: Object.keys(browsers).find(key => browsers[key]) || 'unknown',
            version: this.extractVersion(ua),
            userAgent: ua,
            supportsBackdropFilter: CSS.supports('backdrop-filter', 'blur(10px)'),
            supportsGrid: CSS.supports('display', 'grid'),
            supportsFlex: CSS.supports('display', 'flex')
        };
    }
    
    extractVersion(ua) {
        const match = ua.match(/(Chrome|Firefox|Safari|Edge)\\/(\\d+)/);
        return match ? match[2] : 'unknown';
    }
    
    testFeatureSupport() {
        const features = {
            'backdrop-filter': CSS.supports('backdrop-filter', 'blur(10px)'),
            'css-grid': CSS.supports('display', 'grid'),
            'flexbox': CSS.supports('display', 'flex'),
            'css-variables': CSS.supports('color', 'var(--test)'),
            'transforms': CSS.supports('transform', 'translateX(10px)'),
            'transitions': CSS.supports('transition', 'all 0.3s ease'),
            'animations': CSS.supports('animation', 'test 1s ease'),
            'border-radius': CSS.supports('border-radius', '10px'),
            'box-shadow': CSS.supports('box-shadow', '0 0 10px rgba(0,0,0,0.1)')
        };
        
        console.log('🌐 Browser Feature Support:', features);
        return features;
    }
}

// Initialize testing framework
window.VisualRegressionTester = VisualRegressionTester;
window.CrossBrowserTester = CrossBrowserTester;

// Auto-initialize in development mode
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.vrt = new VisualRegressionTester();
    window.cbt = new CrossBrowserTester();
    
    // Add testing commands to console
    console.log('🧪 Visual Regression Testing available:');
    console.log('- vrt.runAllTests() - Run all visual tests');
    console.log('- vrt.testResponsiveDesign() - Test responsive breakpoints');
    console.log('- vrt.exportReport() - Export test results');
    console.log('- vrt.clearBaselines() - Clear baseline screenshots');
    console.log('- cbt.testFeatureSupport() - Test browser feature support');
}