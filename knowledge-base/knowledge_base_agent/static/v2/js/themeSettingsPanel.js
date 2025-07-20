/* ===== SETTINGS SYSTEM MANAGER ===== */

class SettingsManager {
    constructor() {
        // Modal system
        this.isModalOpen = false;
        this.modal = null;
        this.modalTrigger = null;
        this.modalCloseBtn = null;
        this.modalOverlay = null;
        
        // Compact panel system
        this.isCompactOpen = false;
        this.compactTrigger = null;
        this.compactContent = null;
        this.compactArrow = null;
        
        this.init();
    }
    
    init() {
        // Find modal elements
        this.modalTrigger = document.getElementById('settings-modal-trigger');
        this.modal = document.getElementById('settings-modal');
        this.modalCloseBtn = document.getElementById('settings-modal-close');
        this.modalOverlay = this.modal?.querySelector('.settings-modal-overlay');
        
        // Find compact panel elements
        this.compactTrigger = document.getElementById('compact-settings-toggle');
        this.compactContent = document.getElementById('compact-settings-content');
        this.compactArrow = this.compactTrigger?.querySelector('.compact-settings-arrow');
        
        this.setupEventListeners();
        this.syncThemeSettings();
        console.log('⚙️ Settings Manager initialized');
    }
    
    setupEventListeners() {
        // Modal system event listeners
        if (this.modalTrigger && this.modal) {
            this.modalTrigger.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.openModal();
            });
            
            this.modalCloseBtn?.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.closeModal();
            });
            
            this.modalOverlay?.addEventListener('click', (e) => {
                if (e.target === this.modalOverlay) {
                    this.closeModal();
                }
            });
            
            // Prevent modal content clicks from closing modal
            const modalContent = this.modal?.querySelector('.settings-modal-content');
            modalContent?.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
        
        // Compact panel event listeners
        if (this.compactTrigger && this.compactContent) {
            this.compactTrigger.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleCompactPanel();
            });
        }
        
        // Global event listeners
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (this.isModalOpen) {
                    this.closeModal();
                } else if (this.isCompactOpen) {
                    this.closeCompactPanel();
                }
            }
        });
        
        // Close compact panel when clicking outside
        document.addEventListener('click', (e) => {
            if (this.isCompactOpen && 
                !this.compactTrigger?.contains(e.target) && 
                !this.compactContent?.contains(e.target)) {
                this.closeCompactPanel();
            }
        });
        
        // Theme control event listeners
        this.setupThemeControls();
    }
    
    setupThemeControls() {
        // Wait for theme manager to be available
        const setupControls = () => {
            // Compact theme controls
            const compactLightBtn = document.getElementById('light-mode-compact');
            const compactDarkBtn = document.getElementById('dark-mode-compact');
            const compactAutoBtn = document.getElementById('auto-mode-compact');
            const compactToggle = document.getElementById('theme-toggle-compact');
            
            // Compact color buttons
            const compactColorBtns = document.querySelectorAll('.compact-color-btn');
            
            if (compactLightBtn) {
                compactLightBtn.addEventListener('click', () => {
                    this.setThemeMode('light');
                    this.updateCompactThemeButtons('light');
                });
            }
            
            if (compactDarkBtn) {
                compactDarkBtn.addEventListener('click', () => {
                    this.setThemeMode('dark');
                    this.updateCompactThemeButtons('dark');
                });
            }
            
            if (compactAutoBtn) {
                compactAutoBtn.addEventListener('click', () => {
                    this.setThemeMode('auto');
                    this.updateCompactThemeButtons('auto');
                });
            }
            
            if (compactToggle) {
                compactToggle.addEventListener('change', (e) => {
                    // Legacy toggle: switches between light and dark (ignores auto)
                    const newMode = e.target.checked ? 'dark' : 'light';
                    this.setThemeMode(newMode);
                    this.updateCompactThemeButtons(newMode);
                    
                    // Sync with main theme toggle
                    const mainToggle = document.getElementById('theme-toggle');
                    if (mainToggle) {
                        mainToggle.checked = e.target.checked;
                    }
                });
            }
            
            // Compact color buttons
            compactColorBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    const theme = btn.dataset.theme;
                    this.setAccentColor(theme);
                    this.updateCompactColorButtons(theme);
                });
            });
            
            // Initial sync
            this.syncThemeSettings();
        };
        
        // Setup controls immediately if theme manager is ready, otherwise wait
        if (window.themeManager) {
            setupControls();
        } else {
            // Wait for theme manager to be initialized
            setTimeout(() => {
                if (window.themeManager) {
                    setupControls();
                } else {
                    console.warn('ThemeManager not available for settings sync');
                }
            }, 500);
        }
    }
    
    // Modal methods
    openModal() {
        if (this.isModalOpen || !this.modal) return;
        
        this.modal.classList.remove('hidden');
        this.isModalOpen = true;
        
        // Close compact panel if open
        this.closeCompactPanel();
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Focus first interactive element
        const firstFocusable = this.modal.querySelector('button, input, [tabindex]:not([tabindex="-1"])');
        if (firstFocusable) {
            setTimeout(() => firstFocusable.focus(), 100);
        }
        
        console.log('Settings modal opened');
    }
    
    closeModal() {
        if (!this.isModalOpen || !this.modal) return;
        
        this.modal.classList.add('hidden');
        this.isModalOpen = false;
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Return focus to trigger button
        this.modalTrigger?.focus();
        
        console.log('Settings modal closed');
    }
    
    // Compact panel methods
    toggleCompactPanel() {
        if (this.isCompactOpen) {
            this.closeCompactPanel();
        } else {
            this.openCompactPanel();
        }
    }
    
    openCompactPanel() {
        if (this.isCompactOpen || !this.compactContent) return;
        
        this.compactContent.classList.remove('collapsed');
        this.compactArrow?.classList.add('expanded');
        this.isCompactOpen = true;
        
        console.log('Compact settings panel opened');
    }
    
    closeCompactPanel() {
        if (!this.isCompactOpen || !this.compactContent) return;
        
        this.compactContent.classList.add('collapsed');
        this.compactArrow?.classList.remove('expanded');
        this.isCompactOpen = false;
        
        console.log('Compact settings panel closed');
    }
    
    // Theme management methods
    setThemeMode(mode) {
        // Trigger the main theme manager
        if (window.themeManager && typeof window.themeManager.setThemeMode === 'function') {
            window.themeManager.setThemeMode(mode);
        }
    }
    
    setAccentColor(color) {
        // Trigger the main theme manager
        if (window.themeManager && typeof window.themeManager.setAccentColor === 'function') {
            window.themeManager.setAccentColor(color);
        }
    }
    
    updateCompactThemeButtons(activeMode) {
        const buttons = {
            'light': document.getElementById('light-mode-compact'),
            'dark': document.getElementById('dark-mode-compact'),
            'auto': document.getElementById('auto-mode-compact')
        };
        
        Object.keys(buttons).forEach(mode => {
            const btn = buttons[mode];
            if (btn) {
                btn.classList.toggle('active', mode === activeMode);
            }
        });
    }
    
    updateCompactColorButtons(activeColor) {
        const colorBtns = document.querySelectorAll('.compact-color-btn');
        colorBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === activeColor);
        });
    }
    
    syncThemeSettings() {
        // Sync compact controls with main theme settings
        if (window.themeManager) {
            const currentTheme = window.themeManager.getCurrentTheme();
            if (currentTheme) {
                this.updateCompactThemeButtons(currentTheme.mode);
                this.updateCompactColorButtons(currentTheme.accent);
                
                // Sync toggle switches
                const compactToggle = document.getElementById('theme-toggle-compact');
                const mainToggle = document.getElementById('theme-toggle');
                if (compactToggle && mainToggle) {
                    compactToggle.checked = mainToggle.checked;
                }
            }
        }
    }
    
    // Public API methods
    isSettingsOpen() {
        return this.isModalOpen || this.isCompactOpen;
    }
    
    closeAll() {
        this.closeModal();
        this.closeCompactPanel();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.settingsManager = new SettingsManager();
});

// Make available globally
window.SettingsManager = SettingsManager;