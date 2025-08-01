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
        // Use centralized EventListenerService
        EventListenerService.setupStandardListeners(this, {
            buttons: [
                {
                    selector: '#light-mode-btn',
                    handler: () => this.setThemeMode('light')
                },
                {
                    selector: '#dark-mode-btn',
                    handler: () => this.setThemeMode('dark')
                },
                {
                    selector: '#auto-mode-btn',
                    handler: () => this.setThemeMode('auto')
                }
            ],
            inputs: [
                {
                    selector: '#high-contrast-toggle',
                    events: ['change'],
                    handler: (e) => this.setHighContrast(e.target.checked)
                },
                {
                    selector: '#reduced-motion-toggle',
                    events: ['change'],
                    handler: (e) => this.setReducedMotion(e.target.checked)
                },
                {
                    selector: '#theme-toggle',
                    events: ['change'],
                    handler: (e) => this.setThemeMode(e.target.checked ? 'dark' : 'light')
                }
            ],
            delegated: [
                {
                    selector: '.theme-color-btn',
                    event: 'click',
                    handler: (e, target) => {
                        const theme = target.dataset.theme;
                        if (theme) this.setAccentColor(theme);
                    }
                },
                {
                    selector: '.theme-seasonal-btn',
                    event: 'click',
                    handler: (e, target) => {
                        const theme = target.dataset.theme;
                        if (theme) this.setSeasonalTheme(theme);
                    }
                }
            ]
        });
    }
    
    setupSystemThemeListener() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', (e) => {
            this.systemPrefersDark = e.matches;
            if (this.currentTheme === 'auto') {
                this.applyTheme();
            }
        });
    }
    
    setThemeMode(mode) {
        this.currentTheme = mode;
        this.applyTheme();
        this.updateUI();
        this.savePreferences();
        this.triggerPreviewAnimation();
    }
    
    setAccentColor(color) {
        this.currentAccent = color;
        this.applyTheme();
        this.updateUI();
        this.savePreferences();
        this.triggerPreviewAnimation();
    }
    
    setSeasonalTheme(theme) {
        // Remove existing seasonal themes
        document.body.classList.remove('theme-winter', 'theme-spring', 'theme-summer', 'theme-autumn');
        
        // Apply new seasonal theme
        if (theme) {
            document.body.classList.add(`theme-${theme}`);
        }
        
        this.savePreferences();
        this.triggerPreviewAnimation();
    }
    
    setHighContrast(enabled) {
        this.isHighContrast = enabled;
        document.body.classList.toggle('high-contrast', enabled);
        this.savePreferences();
        this.triggerPreviewAnimation();
    }
    
    setReducedMotion(enabled) {
        this.isReducedMotion = enabled;
        document.body.classList.toggle('reduced-motion', enabled);
        this.savePreferences();
    }
    
    applyTheme() {
        const body = document.body;
        
        // Remove existing theme classes
        body.classList.remove('light-mode', 'dark-mode');
        body.classList.remove('theme-blue', 'theme-purple', 'theme-green', 'theme-orange', 'theme-pink');
        
        // Apply theme mode
        let isDark = false;
        if (this.currentTheme === 'dark') {
            isDark = true;
        } else if (this.currentTheme === 'auto') {
            isDark = this.systemPrefersDark;
        }
        
        body.classList.add(isDark ? 'dark-mode' : 'light-mode');
        
        // Apply accent color
        body.classList.add(`theme-${this.currentAccent}`);
        
        // Apply accessibility settings
        body.classList.toggle('high-contrast', this.isHighContrast);
        body.classList.toggle('reduced-motion', this.isReducedMotion);
        
        // Update meta theme-color for mobile browsers
        this.updateMetaThemeColor(isDark);
    }
    
    updateMetaThemeColor(isDark) {
        let metaThemeColor = document.querySelector('meta[name=\"theme-color\"]');
        if (!metaThemeColor) {
            metaThemeColor = document.createElement('meta');
            metaThemeColor.name = 'theme-color';
            document.head.appendChild(metaThemeColor);
        }
        
        const color = isDark ? '#0f172a' : '#ffffff';
        metaThemeColor.content = color;
    }
    
    updateUI() {
        // Update theme mode buttons
        document.querySelectorAll('.theme-mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeMode = document.getElementById(`${this.currentTheme}-mode-btn`);
        if (activeMode) {
            activeMode.classList.add('active');
        }
        
        // Update accent color buttons
        document.querySelectorAll('.theme-color-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        const activeColor = document.querySelector(`[data-theme=\"${this.currentAccent}\"]`);
        if (activeColor) {
            activeColor.classList.add('active');
        }
        
        // Update accessibility toggles
        const highContrastToggle = document.getElementById('high-contrast-toggle');
        if (highContrastToggle) {
            highContrastToggle.checked = this.isHighContrast;
        }
        
        const reducedMotionToggle = document.getElementById('reduced-motion-toggle');
        if (reducedMotionToggle) {
            reducedMotionToggle.checked = this.isReducedMotion;
        }
        
        // Update legacy toggle
        const legacyToggle = document.getElementById('theme-toggle');
        if (legacyToggle) {
            legacyToggle.checked = this.currentTheme === 'dark' || 
                                  (this.currentTheme === 'auto' && this.systemPrefersDark);
        }
    }
    
    triggerPreviewAnimation() {
        document.body.classList.add('theme-preview-animation');
        setTimeout(() => {
            document.body.classList.remove('theme-preview-animation');
        }, 300);
    }
    
    savePreferences() {
        const preferences = {
            theme: this.currentTheme,
            accent: this.currentAccent,
            highContrast: this.isHighContrast,
            reducedMotion: this.isReducedMotion
        };
        
        localStorage.setItem('themePreferences', JSON.stringify(preferences));
    }
    
    loadPreferences() {
        try {
            const saved = localStorage.getItem('themePreferences');
            if (saved) {
                const preferences = JSON.parse(saved);
                this.currentTheme = preferences.theme || 'auto';
                this.currentAccent = preferences.accent || 'blue';
                this.isHighContrast = preferences.highContrast || false;
                this.isReducedMotion = preferences.reducedMotion || false;
            }
        } catch (error) {
            console.warn('Failed to load theme preferences:', error);
        }
    }
    
    // Public API methods
    getCurrentTheme() {
        return {
            mode: this.currentTheme,
            accent: this.currentAccent,
            highContrast: this.isHighContrast,
            reducedMotion: this.isReducedMotion,
            isDark: this.currentTheme === 'dark' || 
                   (this.currentTheme === 'auto' && this.systemPrefersDark)
        };
    }
    
    resetToDefaults() {
        this.currentTheme = 'auto';
        this.currentAccent = 'blue';
        this.isHighContrast = false;
        this.isReducedMotion = false;
        
        // Remove seasonal themes
        document.body.classList.remove('theme-winter', 'theme-spring', 'theme-summer', 'theme-autumn');
        
        this.applyTheme();
        this.updateUI();
        this.savePreferences();
        this.triggerPreviewAnimation();
    }
    
    exportTheme() {
        const theme = this.getCurrentTheme();
        const blob = new Blob([JSON.stringify(theme, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'theme-settings.json';
        a.click();
        URL.revokeObjectURL(url);
    }
    
    importTheme(themeData) {
        try {
            if (typeof themeData === 'string') {
                themeData = JSON.parse(themeData);
            }
            
            this.currentTheme = themeData.mode || 'auto';
            this.currentAccent = themeData.accent || 'blue';
            this.isHighContrast = themeData.highContrast || false;
            this.isReducedMotion = themeData.reducedMotion || false;
            
            this.applyTheme();
            this.updateUI();
            this.savePreferences();
            this.triggerPreviewAnimation();
            
            return true;
        } catch (error) {
            console.error('Failed to import theme:', error);
            return false;
        }
    }
}

// Initialize theme manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});

// Make ThemeManager globally available
window.ThemeManager = ThemeManager;