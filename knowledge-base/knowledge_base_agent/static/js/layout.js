/**
 * Layout Management Module
 * Minimal responsive handling - CSS flexbox handles the main layout
 */

class LayoutManager {
    constructor() {
        this.isInitialized = false;
    }

    /**
     * Initialize layout management
     */
    init() {
        if (this.isInitialized) return;
        
        console.log('LayoutManager: Initializing minimal layout management...');
        
        // Only handle window resize for responsive adjustments
        window.addEventListener('resize', () => {
            this.handleResize();
        });
        
        this.isInitialized = true;
        console.log('LayoutManager: Initialized');
    }

    /**
     * Handle window resize for responsive behavior
     */
    handleResize() {
        // Let CSS flexbox handle the layout
        // Only log for debugging if needed
        console.log('LayoutManager: Window resized - CSS flexbox handling layout');
    }

    /**
     * Legacy method - no longer needed as CSS handles height matching
     * @deprecated Use CSS flexbox instead
     */
    adjustPanelHeights() {
        console.log('LayoutManager: adjustPanelHeights called but not needed - CSS flexbox handles this');
        // Intentionally empty - CSS flexbox handles height matching
    }

    /**
     * Legacy method - no longer manipulates DOM
     * @deprecated 
     */
    ensureDOMStructure() {
        console.log('LayoutManager: DOM structure verification skipped - using natural HTML structure');
        // Intentionally empty - no DOM manipulation
    }

    /**
     * Legacy trigger method
     * @deprecated
     */
    triggerHeightAdjustment() {
        // Intentionally empty - CSS handles this
    }
}

// Export singleton instance
window.layoutManager = new LayoutManager(); 