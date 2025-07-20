/* ===== THEME MANAGER ===== */

class ThemeManager {
    constructor() {
        this.currentTheme = 'auto';
        this.currentAccent = 'blue';
        this.isHighContrast = false;
        this.isReducedMotion = false;
        this.systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        this.init();
    }
    
    init() {
        // Load saved preferences
        this.loadPreferences();
        
        // Apply initial theme
        this.applyTheme();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Listen for system theme changes
        this.setupSystemThemeListener();
        
        // Update UI to reflect current settings
        this.updateUI();
        
        console.log('🎨 ThemeManager initialized');
    }
    
    setupEventListeners() {
        // No need for panel toggle listeners since we're using a modal now
        // The modal is handled by SettingsModal class
        
        // Theme mode buttons
        document.getElementById('light-mode-btn')?.addEventListener('click', () => {
            this.setThemeMode('light');
        });
        
        document.getElementById('dark-mode-btn')?.addEventListener('click', () => {
            this.setThemeMode('dark');
        });
        
        document.getElementById('auto-mode-btn')?.addEventListener('click', () => {
            this.setThemeMode('auto');
        });
        
        // Accent color buttons
        document.querySelectorAll('.theme-color-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const theme = btn.dataset.theme;
                this.setAccentColor(theme);
            });
        });
        
        // Seasonal theme buttons
        document.querySelectorAll('.theme-seasonal-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const theme = btn.dataset.theme;
                this.setSeasonalTheme(theme);
            });
        });
        
        // Accessibility toggles
        document.getElementById('high-contrast-toggle')?.addEventListener('change', (e) => {
            this.setHighContrast(e.target.checked);
        });
        
        document.getElementById('reduced-motion-toggle')?.addEventListener('change', (e) => {
            this.setReducedMotion(e.target.checked);
        });
        
        // Legacy theme toggle (for backward compatibility)
        document.getElementById('theme-toggle')?.addEventListener('change', (e) => {
            this.setThemeMode(e.target.checked ? 'dark' : 'light');
        });
    }
    
    setupSystemThemeListener() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');\n        mediaQuery.addEventListener('change', (e) => {\n            this.systemPrefersDark = e.matches;\n            if (this.currentTheme === 'auto') {\n                this.applyTheme();\n            }\n        });\n    }\n    \n    setThemeMode(mode) {\n        this.currentTheme = mode;\n        this.applyTheme();\n        this.updateUI();\n        this.savePreferences();\n        this.triggerPreviewAnimation();\n    }\n    \n    setAccentColor(color) {\n        this.currentAccent = color;\n        this.applyTheme();\n        this.updateUI();\n        this.savePreferences();\n        this.triggerPreviewAnimation();\n    }\n    \n    setSeasonalTheme(theme) {\n        // Remove existing seasonal themes\n        document.body.classList.remove('theme-winter', 'theme-spring', 'theme-summer', 'theme-autumn');\n        \n        // Apply new seasonal theme\n        if (theme) {\n            document.body.classList.add(`theme-${theme}`);\n        }\n        \n        this.savePreferences();\n        this.triggerPreviewAnimation();\n    }\n    \n    setHighContrast(enabled) {\n        this.isHighContrast = enabled;\n        document.body.classList.toggle('high-contrast', enabled);\n        this.savePreferences();\n        this.triggerPreviewAnimation();\n    }\n    \n    setReducedMotion(enabled) {\n        this.isReducedMotion = enabled;\n        document.body.classList.toggle('reduced-motion', enabled);\n        this.savePreferences();\n    }\n    \n    applyTheme() {\n        const body = document.body;\n        \n        // Remove existing theme classes\n        body.classList.remove('light-mode', 'dark-mode');\n        body.classList.remove('theme-blue', 'theme-purple', 'theme-green', 'theme-orange', 'theme-pink');\n        \n        // Apply theme mode\n        let isDark = false;\n        if (this.currentTheme === 'dark') {\n            isDark = true;\n        } else if (this.currentTheme === 'auto') {\n            isDark = this.systemPrefersDark;\n        }\n        \n        body.classList.add(isDark ? 'dark-mode' : 'light-mode');\n        \n        // Apply accent color\n        body.classList.add(`theme-${this.currentAccent}`);\n        \n        // Apply accessibility settings\n        body.classList.toggle('high-contrast', this.isHighContrast);\n        body.classList.toggle('reduced-motion', this.isReducedMotion);\n        \n        // Update meta theme-color for mobile browsers\n        this.updateMetaThemeColor(isDark);\n    }\n    \n    updateMetaThemeColor(isDark) {\n        let metaThemeColor = document.querySelector('meta[name=\"theme-color\"]');\n        if (!metaThemeColor) {\n            metaThemeColor = document.createElement('meta');\n            metaThemeColor.name = 'theme-color';\n            document.head.appendChild(metaThemeColor);\n        }\n        \n        const color = isDark ? '#0f172a' : '#ffffff';\n        metaThemeColor.content = color;\n    }\n    \n    updateUI() {\n        // Update theme mode buttons\n        document.querySelectorAll('.theme-mode-btn').forEach(btn => {\n            btn.classList.remove('active');\n        });\n        \n        const activeMode = document.getElementById(`${this.currentTheme}-mode-btn`);\n        if (activeMode) {\n            activeMode.classList.add('active');\n        }\n        \n        // Update accent color buttons\n        document.querySelectorAll('.theme-color-btn').forEach(btn => {\n            btn.classList.remove('active');\n        });\n        \n        const activeColor = document.querySelector(`[data-theme=\"${this.currentAccent}\"]`);\n        if (activeColor) {\n            activeColor.classList.add('active');\n        }\n        \n        // Update accessibility toggles\n        const highContrastToggle = document.getElementById('high-contrast-toggle');\n        if (highContrastToggle) {\n            highContrastToggle.checked = this.isHighContrast;\n        }\n        \n        const reducedMotionToggle = document.getElementById('reduced-motion-toggle');\n        if (reducedMotionToggle) {\n            reducedMotionToggle.checked = this.isReducedMotion;\n        }\n        \n        // Update legacy toggle\n        const legacyToggle = document.getElementById('theme-toggle');\n        if (legacyToggle) {\n            legacyToggle.checked = this.currentTheme === 'dark' || \n                                  (this.currentTheme === 'auto' && this.systemPrefersDark);\n        }\n    }\n    \n    triggerPreviewAnimation() {\n        document.body.classList.add('theme-preview-animation');\n        setTimeout(() => {\n            document.body.classList.remove('theme-preview-animation');\n        }, 300);\n    }\n    \n    savePreferences() {\n        const preferences = {\n            theme: this.currentTheme,\n            accent: this.currentAccent,\n            highContrast: this.isHighContrast,\n            reducedMotion: this.isReducedMotion\n        };\n        \n        localStorage.setItem('themePreferences', JSON.stringify(preferences));\n    }\n    \n    loadPreferences() {\n        try {\n            const saved = localStorage.getItem('themePreferences');\n            if (saved) {\n                const preferences = JSON.parse(saved);\n                this.currentTheme = preferences.theme || 'auto';\n                this.currentAccent = preferences.accent || 'blue';\n                this.isHighContrast = preferences.highContrast || false;\n                this.isReducedMotion = preferences.reducedMotion || false;\n            }\n        } catch (error) {\n            console.warn('Failed to load theme preferences:', error);\n        }\n    }\n    \n    // Public API methods\n    getCurrentTheme() {\n        return {\n            mode: this.currentTheme,\n            accent: this.currentAccent,\n            highContrast: this.isHighContrast,\n            reducedMotion: this.isReducedMotion,\n            isDark: this.currentTheme === 'dark' || \n                   (this.currentTheme === 'auto' && this.systemPrefersDark)\n        };\n    }\n    \n    resetToDefaults() {\n        this.currentTheme = 'auto';\n        this.currentAccent = 'blue';\n        this.isHighContrast = false;\n        this.isReducedMotion = false;\n        \n        // Remove seasonal themes\n        document.body.classList.remove('theme-winter', 'theme-spring', 'theme-summer', 'theme-autumn');\n        \n        this.applyTheme();\n        this.updateUI();\n        this.savePreferences();\n        this.triggerPreviewAnimation();\n    }\n    \n    exportTheme() {\n        const theme = this.getCurrentTheme();\n        const blob = new Blob([JSON.stringify(theme, null, 2)], { type: 'application/json' });\n        const url = URL.createObjectURL(blob);\n        const a = document.createElement('a');\n        a.href = url;\n        a.download = 'theme-settings.json';\n        a.click();\n        URL.revokeObjectURL(url);\n    }\n    \n    importTheme(themeData) {\n        try {\n            if (typeof themeData === 'string') {\n                themeData = JSON.parse(themeData);\n            }\n            \n            this.currentTheme = themeData.mode || 'auto';\n            this.currentAccent = themeData.accent || 'blue';\n            this.isHighContrast = themeData.highContrast || false;\n            this.isReducedMotion = themeData.reducedMotion || false;\n            \n            this.applyTheme();\n            this.updateUI();\n            this.savePreferences();\n            this.triggerPreviewAnimation();\n            \n            return true;\n        } catch (error) {\n            console.error('Failed to import theme:', error);\n            return false;\n        }\n    }\n}\n\n// Initialize theme manager when DOM is ready\ndocument.addEventListener('DOMContentLoaded', () => {\n    window.themeManager = new ThemeManager();\n});\n\n// Make ThemeManager globally available\nwindow.ThemeManager = ThemeManager;