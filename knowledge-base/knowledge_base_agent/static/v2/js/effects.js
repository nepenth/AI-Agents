/* V2 EFFECTS.JS - VISUAL UI ENHANCEMENTS */

class UIEffects {
    constructor() {
        // This class is reserved for future UI effects.
        // The previous mouse-tracking light effect has been removed per user feedback.
        this.initLiquidGlassEffect();
    }

    initLiquidGlassEffect() {
        const interactiveElements = document.querySelectorAll('.panel, .btn, .nav-link, .phase-item, .preference-btn');

        interactiveElements.forEach(element => {
            element.addEventListener('mousemove', (e) => {
                const rect = element.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                element.style.setProperty('--mouse-x', `${x}px`);
                element.style.setProperty('--mouse-y', `${y}px`);
            });
        });
    }
}

// Make globally available for non-module usage
window.UIEffects = UIEffects; 