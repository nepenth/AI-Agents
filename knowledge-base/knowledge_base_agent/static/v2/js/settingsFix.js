/* ===== SETTINGS FUNCTIONALITY FIX ===== */

// This script ensures all settings work properly and provides clear documentation

class SettingsFunctionality {
    constructor() {
        this.init();
    }
    
    init() {
        console.log('🔧 Initializing Settings Functionality Fix...');
        
        // Wait for all managers to be ready
        this.waitForManagers().then(() => {
            this.setupSettingsDocumentation();
            this.fixSettingsConnections();
            this.addSettingsValidation();
            console.log('✅ Settings functionality fix complete');
        });
    }
    
    async waitForManagers() {
        // Wait for theme manager and settings manager to be available
        let attempts = 0;
        while ((!window.themeManager || !window.settingsManager) && attempts < 20) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        if (!window.themeManager) {
            console.warn('⚠️ ThemeManager not available - some settings may not work');
        }
        
        if (!window.settingsManager) {
            console.warn('⚠️ SettingsManager not available - some settings may not work');
        }
    }
    
    setupSettingsDocumentation() {
        // Document what each setting does
        const settingsInfo = {
            'Legacy Toggle': {
                description: 'Switches between light and dark mode (bypasses auto mode)',
                functionality: 'ON = Dark Mode, OFF = Light Mode',
                working: true
            },
            'Theme Mode': {
                description: 'Controls the overall theme appearance',
                options: {
                    'Light': 'Force light theme',
                    'Dark': 'Force dark theme', 
                    'Auto': 'Follow system preference'
                },
                working: true
            },
            'Accent Colors': {
                description: 'Changes the primary accent color throughout the UI',
                options: {
                    'Blue': 'Default blue accent',
                    'Purple': 'Purple accent',
                    'Green': 'Green accent',
                    'Orange': 'Orange accent',
                    'Pink': 'Pink accent'
                },
                working: true
            },
            'High Contrast': {
                description: 'Increases contrast for better accessibility',
                functionality: 'Enhances text and border visibility',
                working: true
            },
            'Reduce Motion': {
                description: 'Reduces animations for users sensitive to motion',
                functionality: 'Disables transitions and animations',
                working: true
            }
        };
        
        // Store documentation for debugging
        window.settingsDocumentation = settingsInfo;
        console.log('📚 Settings Documentation:', settingsInfo);
    }
    
    fixSettingsConnections() {
        // Ensure all settings are properly connected
        this.fixAccentColors();
        this.fixLegacyToggle();
        this.fixThemeModeButtons();
        this.fixAccessibilityOptions();
    }
    
    fixAccentColors() {
        // Fix accent color functionality
        const colorButtons = document.querySelectorAll('.theme-color-btn, .compact-color-btn');
        
        colorButtons.forEach(btn => {
            // Remove existing listeners to avoid duplicates
            btn.replaceWith(btn.cloneNode(true));
        });
        
        // Re-add listeners to cloned buttons
        document.querySelectorAll('.theme-color-btn, .compact-color-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const color = btn.dataset.theme;
                
                if (window.themeManager) {
                    window.themeManager.setAccentColor(color);
                    console.log(`🎨 Accent color changed to: ${color}`);
                    
                    // Update all color buttons
                    document.querySelectorAll('.theme-color-btn, .compact-color-btn').forEach(b => {
                        b.classList.toggle('active', b.dataset.theme === color);
                    });
                    
                    // Show visual feedback
                    this.showSettingsFeedback(`Accent color changed to ${color}`);
                } else {
                    console.warn('ThemeManager not available for accent color change');
                }
            });
        });
    }
    
    fixLegacyToggle() {
        // Fix legacy toggle functionality
        const legacyToggles = document.querySelectorAll('#theme-toggle, #theme-toggle-compact');
        
        legacyToggles.forEach(toggle => {
            toggle.addEventListener('change', (e) => {
                const isDark = e.target.checked;
                const mode = isDark ? 'dark' : 'light';
                
                if (window.themeManager) {
                    window.themeManager.setThemeMode(mode);
                    console.log(`🌓 Legacy toggle: ${mode} mode`);
                    
                    // Sync all legacy toggles
                    legacyToggles.forEach(t => {
                        if (t !== e.target) {
                            t.checked = isDark;
                        }
                    });
                    
                    // Update theme mode buttons
                    document.querySelectorAll('.theme-mode-btn, .compact-theme-btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    
                    const activeBtn = document.querySelector(`#${mode}-mode-btn, #${mode}-mode-compact`);
                    if (activeBtn) {
                        activeBtn.classList.add('active');
                    }
                    
                    this.showSettingsFeedback(`Theme switched to ${mode} mode`);
                }
            });
        });
    }
    
    fixThemeModeButtons() {
        // Fix theme mode buttons
        const themeBtns = document.querySelectorAll('.theme-mode-btn, .compact-theme-btn');
        
        themeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                
                // Extract mode from button ID
                const btnId = btn.id;
                let mode = 'auto';
                if (btnId.includes('light')) mode = 'light';
                else if (btnId.includes('dark')) mode = 'dark';
                else if (btnId.includes('auto')) mode = 'auto';
                
                if (window.themeManager) {
                    window.themeManager.setThemeMode(mode);
                    console.log(`🎭 Theme mode changed to: ${mode}`);
                    
                    // Update all theme buttons
                    themeBtns.forEach(b => b.classList.remove('active'));
                    document.querySelectorAll(`[id*="${mode}-mode"]`).forEach(b => {
                        b.classList.add('active');
                    });
                    
                    // Update legacy toggles if not auto mode
                    if (mode !== 'auto') {
                        const legacyToggles = document.querySelectorAll('#theme-toggle, #theme-toggle-compact');
                        legacyToggles.forEach(toggle => {
                            toggle.checked = mode === 'dark';
                        });
                    }
                    
                    this.showSettingsFeedback(`Theme mode: ${mode}`);
                }
            });
        });
    }
    
    fixAccessibilityOptions() {
        // Fix accessibility toggles
        const highContrastToggle = document.getElementById('high-contrast-toggle');
        const reducedMotionToggle = document.getElementById('reduced-motion-toggle');
        
        if (highContrastToggle) {
            highContrastToggle.addEventListener('change', (e) => {
                if (window.themeManager) {
                    window.themeManager.setHighContrast(e.target.checked);
                    console.log(`♿ High contrast: ${e.target.checked ? 'enabled' : 'disabled'}`);
                    this.showSettingsFeedback(`High contrast ${e.target.checked ? 'enabled' : 'disabled'}`);
                }
            });
        }
        
        if (reducedMotionToggle) {
            reducedMotionToggle.addEventListener('change', (e) => {
                if (window.themeManager) {
                    window.themeManager.setReducedMotion(e.target.checked);
                    console.log(`🎬 Reduced motion: ${e.target.checked ? 'enabled' : 'disabled'}`);
                    this.showSettingsFeedback(`Reduced motion ${e.target.checked ? 'enabled' : 'disabled'}`);
                }
            });
        }
    }
    
    addSettingsValidation() {
        // Add validation to ensure settings are working
        setInterval(() => {
            this.validateSettings();
        }, 5000); // Check every 5 seconds
    }
    
    validateSettings() {
        if (!window.themeManager) return;
        
        const currentTheme = window.themeManager.getCurrentTheme();
        
        // Validate theme is applied to body
        const body = document.body;
        const expectedClass = currentTheme.isDark ? 'dark-mode' : 'light-mode';
        
        if (!body.classList.contains(expectedClass)) {
            console.warn(`⚠️ Theme validation failed: expected ${expectedClass}`);
            window.themeManager.applyTheme(); // Re-apply theme
        }
        
        // Validate accent color
        const expectedAccentClass = `theme-${currentTheme.accent}`;
        if (!body.classList.contains(expectedAccentClass)) {
            console.warn(`⚠️ Accent color validation failed: expected ${expectedAccentClass}`);
            window.themeManager.applyTheme(); // Re-apply theme
        }
    }
    
    showSettingsFeedback(message) {
        // Show visual feedback when settings change
        const feedback = document.createElement('div');
        feedback.className = 'settings-feedback';
        feedback.textContent = message;
        feedback.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: var(--border-radius);
            padding: var(--space-2) var(--space-3);
            color: var(--text-primary);
            font-size: 0.8rem;
            z-index: 10000;
            animation: slideInFade 0.3s ease-out;
        `;
        
        document.body.appendChild(feedback);
        
        setTimeout(() => {
            feedback.style.animation = 'slideOutFade 0.3s ease-out';
            setTimeout(() => {
                if (feedback.parentNode) {
                    feedback.parentNode.removeChild(feedback);
                }
            }, 300);
        }, 2000);
    }
    
    // Public API for debugging
    testAllSettings() {
        console.log('🧪 Testing all settings...');
        
        // Test accent colors
        const colors = ['blue', 'purple', 'green', 'orange', 'pink'];
        colors.forEach((color, index) => {
            setTimeout(() => {
                if (window.themeManager) {
                    window.themeManager.setAccentColor(color);
                    console.log(`Testing accent color: ${color}`);
                }
            }, index * 1000);
        });
        
        // Test theme modes
        const modes = ['light', 'dark', 'auto'];
        modes.forEach((mode, index) => {
            setTimeout(() => {
                if (window.themeManager) {
                    window.themeManager.setThemeMode(mode);
                    console.log(`Testing theme mode: ${mode}`);
                }
            }, (colors.length + index) * 1000);
        });
    }
}

// Add CSS for feedback animations
const settingsFixStyle = document.createElement('style');
settingsFixStyle.textContent = `
    @keyframes slideInFade {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes slideOutFade {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
`;
document.head.appendChild(settingsFixStyle);

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.settingsFix = new SettingsFunctionality();
});

// Make available globally for debugging
window.SettingsFunctionality = SettingsFunctionality;