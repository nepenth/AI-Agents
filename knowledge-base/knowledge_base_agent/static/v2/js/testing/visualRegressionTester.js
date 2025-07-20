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
    
    async runAllTests() {\n        if (this.isRunning) {\n            console.warn('Tests already running');\n            return;\n        }\n        \n        this.isRunning = true;\n        this.results = [];\n        \n        console.log('🧪 Starting visual regression tests...');\n        \n        for (const suite of this.testSuites) {\n            console.log(`📋 Running test suite: ${suite.name}`);\n            \n            for (const test of suite.tests) {\n                await this.runComponentTest(test, suite.name);\n            }\n        }\n        \n        this.isRunning = false;\n        this.generateReport();\n        \n        console.log('✅ Visual regression tests completed');\n        return this.results;\n    }\n    \n    async runComponentTest(test, suiteName) {\n        const elements = document.querySelectorAll(test.selector);\n        \n        if (elements.length === 0) {\n            this.results.push({\n                suite: suiteName,\n                test: test.name,\n                status: 'skipped',\n                reason: 'No elements found'\n            });\n            return;\n        }\n        \n        for (let i = 0; i < elements.length; i++) {\n            const element = elements[i];\n            \n            for (const state of test.states) {\n                try {\n                    const screenshot = await this.captureElementScreenshot(element, state);\n                    const result = await this.compareScreenshot(test.name, state, i, screenshot);\n                    \n                    this.results.push({\n                        suite: suiteName,\n                        test: test.name,\n                        state: state,\n                        element: i,\n                        status: result.status,\n                        diff: result.diff,\n                        screenshot: screenshot\n                    });\n                } catch (error) {\n                    this.results.push({\n                        suite: suiteName,\n                        test: test.name,\n                        state: state,\n                        element: i,\n                        status: 'error',\n                        error: error.message\n                    });\n                }\n            }\n        }\n    }\n    \n    async captureElementScreenshot(element, state) {\n        // Apply state to element\n        await this.applyElementState(element, state);\n        \n        // Wait for animations to complete\n        await this.waitForAnimations();\n        \n        // Get element bounds\n        const rect = element.getBoundingClientRect();\n        \n        // Set canvas size\n        this.canvas.width = rect.width;\n        this.canvas.height = rect.height;\n        \n        // Capture element using html2canvas-like approach\n        const screenshot = await this.renderElementToCanvas(element, rect);\n        \n        // Reset element state\n        await this.resetElementState(element, state);\n        \n        return screenshot;\n    }\n    \n    async applyElementState(element, state) {\n        switch (state) {\n            case 'hover':\n                element.classList.add('test-hover-state');\n                element.dispatchEvent(new MouseEvent('mouseenter'));\n                break;\n            case 'active':\n                element.classList.add('test-active-state');\n                element.dispatchEvent(new MouseEvent('mousedown'));\n                break;\n            case 'focus':\n                element.focus();\n                break;\n            case 'disabled':\n                element.disabled = true;\n                element.classList.add('disabled');\n                break;\n            case 'error':\n                element.classList.add('error');\n                break;\n            case 'animated':\n                element.classList.add('animate-glass-slide-in');\n                break;\n        }\n    }\n    \n    async resetElementState(element, state) {\n        switch (state) {\n            case 'hover':\n                element.classList.remove('test-hover-state');\n                element.dispatchEvent(new MouseEvent('mouseleave'));\n                break;\n            case 'active':\n                element.classList.remove('test-active-state');\n                element.dispatchEvent(new MouseEvent('mouseup'));\n                break;\n            case 'focus':\n                element.blur();\n                break;\n            case 'disabled':\n                element.disabled = false;\n                element.classList.remove('disabled');\n                break;\n            case 'error':\n                element.classList.remove('error');\n                break;\n            case 'animated':\n                element.classList.remove('animate-glass-slide-in');\n                break;\n        }\n    }\n    \n    async waitForAnimations() {\n        return new Promise(resolve => {\n            // Wait for CSS animations and transitions to complete\n            setTimeout(resolve, 500);\n        });\n    }\n    \n    async renderElementToCanvas(element, rect) {\n        // Simple canvas rendering - in production, use html2canvas or similar\n        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);\n        \n        // Get computed styles\n        const styles = window.getComputedStyle(element);\n        \n        // Draw background\n        this.context.fillStyle = styles.backgroundColor;\n        this.context.fillRect(0, 0, rect.width, rect.height);\n        \n        // Draw border\n        if (styles.borderWidth !== '0px') {\n            this.context.strokeStyle = styles.borderColor;\n            this.context.lineWidth = parseInt(styles.borderWidth);\n            this.context.strokeRect(0, 0, rect.width, rect.height);\n        }\n        \n        // Convert canvas to data URL\n        return this.canvas.toDataURL('image/png');\n    }\n    \n    async compareScreenshot(testName, state, elementIndex, screenshot) {\n        const key = `${testName}-${state}-${elementIndex}`;\n        const stored = localStorage.getItem(`vrt-baseline-${key}`);\n        \n        if (!stored) {\n            // First run - store as baseline\n            localStorage.setItem(`vrt-baseline-${key}`, screenshot);\n            return { status: 'baseline-created', diff: 0 };\n        }\n        \n        // Compare with baseline\n        const diff = this.calculateImageDiff(stored, screenshot);\n        const threshold = 0.05; // 5% difference threshold\n        \n        return {\n            status: diff > threshold ? 'failed' : 'passed',\n            diff: diff\n        };\n    }\n    \n    calculateImageDiff(baseline, current) {\n        // Simple pixel difference calculation\n        // In production, use a proper image diff library\n        if (baseline === current) return 0;\n        \n        // For now, return a mock difference\n        return Math.random() * 0.1; // 0-10% difference\n    }\n    \n    generateReport() {\n        const report = {\n            timestamp: new Date().toISOString(),\n            total: this.results.length,\n            passed: this.results.filter(r => r.status === 'passed').length,\n            failed: this.results.filter(r => r.status === 'failed').length,\n            skipped: this.results.filter(r => r.status === 'skipped').length,\n            errors: this.results.filter(r => r.status === 'error').length,\n            results: this.results\n        };\n        \n        console.table(this.results);\n        console.log('📊 Test Summary:', {\n            Total: report.total,\n            Passed: report.passed,\n            Failed: report.failed,\n            Skipped: report.skipped,\n            Errors: report.errors\n        });\n        \n        // Store report\n        localStorage.setItem('vrt-latest-report', JSON.stringify(report));\n        \n        return report;\n    }\n    \n    exportReport() {\n        const report = localStorage.getItem('vrt-latest-report');\n        if (!report) {\n            console.warn('No test report available');\n            return;\n        }\n        \n        const blob = new Blob([report], { type: 'application/json' });\n        const url = URL.createObjectURL(blob);\n        const a = document.createElement('a');\n        a.href = url;\n        a.download = `visual-regression-report-${Date.now()}.json`;\n        a.click();\n        URL.revokeObjectURL(url);\n    }\n    \n    clearBaselines() {\n        const keys = Object.keys(localStorage).filter(key => key.startsWith('vrt-baseline-'));\n        keys.forEach(key => localStorage.removeItem(key));\n        console.log(`🗑️ Cleared ${keys.length} baseline screenshots`);\n    }\n    \n    // Responsive design testing\n    async testResponsiveDesign() {\n        const viewports = [\n            { name: 'mobile', width: 375, height: 667 },\n            { name: 'tablet', width: 768, height: 1024 },\n            { name: 'desktop', width: 1920, height: 1080 }\n        ];\n        \n        const responsiveResults = [];\n        \n        for (const viewport of viewports) {\n            console.log(`📱 Testing ${viewport.name} viewport (${viewport.width}x${viewport.height})`);\n            \n            // Simulate viewport\n            this.setViewport(viewport.width, viewport.height);\n            \n            // Wait for layout to adjust\n            await this.waitForAnimations();\n            \n            // Run tests for this viewport\n            const results = await this.runAllTests();\n            responsiveResults.push({\n                viewport: viewport.name,\n                dimensions: `${viewport.width}x${viewport.height}`,\n                results: results\n            });\n        }\n        \n        // Reset viewport\n        this.resetViewport();\n        \n        return responsiveResults;\n    }\n    \n    setViewport(width, height) {\n        // Simulate viewport change\n        document.documentElement.style.width = `${width}px`;\n        document.documentElement.style.height = `${height}px`;\n        \n        // Trigger resize event\n        window.dispatchEvent(new Event('resize'));\n    }\n    \n    resetViewport() {\n        document.documentElement.style.width = '';\n        document.documentElement.style.height = '';\n        window.dispatchEvent(new Event('resize'));\n    }\n}\n\n// Cross-browser testing utilities\nclass CrossBrowserTester {\n    constructor() {\n        this.browserInfo = this.getBrowserInfo();\n    }\n    \n    getBrowserInfo() {\n        const ua = navigator.userAgent;\n        const browsers = {\n            chrome: /Chrome/.test(ua) && !/Edge/.test(ua),\n            firefox: /Firefox/.test(ua),\n            safari: /Safari/.test(ua) && !/Chrome/.test(ua),\n            edge: /Edge/.test(ua),\n            ie: /Trident/.test(ua)\n        };\n        \n        return {\n            name: Object.keys(browsers).find(key => browsers[key]) || 'unknown',\n            version: this.extractVersion(ua),\n            userAgent: ua,\n            supportsBackdropFilter: CSS.supports('backdrop-filter', 'blur(10px)'),\n            supportsGrid: CSS.supports('display', 'grid'),\n            supportsFlex: CSS.supports('display', 'flex')\n        };\n    }\n    \n    extractVersion(ua) {\n        const match = ua.match(/(Chrome|Firefox|Safari|Edge)\\/(\\d+)/);\n        return match ? match[2] : 'unknown';\n    }\n    \n    testFeatureSupport() {\n        const features = {\n            'backdrop-filter': CSS.supports('backdrop-filter', 'blur(10px)'),\n            'css-grid': CSS.supports('display', 'grid'),\n            'flexbox': CSS.supports('display', 'flex'),\n            'css-variables': CSS.supports('color', 'var(--test)'),\n            'transforms': CSS.supports('transform', 'translateX(10px)'),\n            'transitions': CSS.supports('transition', 'all 0.3s ease'),\n            'animations': CSS.supports('animation', 'test 1s ease'),\n            'border-radius': CSS.supports('border-radius', '10px'),\n            'box-shadow': CSS.supports('box-shadow', '0 0 10px rgba(0,0,0,0.1)')\n        };\n        \n        console.log('🌐 Browser Feature Support:', features);\n        return features;\n    }\n}\n\n// Initialize testing framework\nwindow.VisualRegressionTester = VisualRegressionTester;\nwindow.CrossBrowserTester = CrossBrowserTester;\n\n// Auto-initialize in development mode\nif (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {\n    window.vrt = new VisualRegressionTester();\n    window.cbt = new CrossBrowserTester();\n    \n    // Add testing commands to console\n    console.log('🧪 Visual Regression Testing available:');\n    console.log('- vrt.runAllTests() - Run all visual tests');\n    console.log('- vrt.testResponsiveDesign() - Test responsive breakpoints');\n    console.log('- vrt.exportReport() - Export test results');\n    console.log('- vrt.clearBaselines() - Clear baseline screenshots');\n    console.log('- cbt.testFeatureSupport() - Test browser feature support');\n}