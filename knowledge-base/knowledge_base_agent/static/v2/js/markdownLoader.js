/**
 * Markdown Loader - Dynamically loads markdown-it library
 * 
 * This module handles loading the markdown-it library from CDN
 * with fallback options for enhanced message rendering.
 */
class MarkdownLoader {
    constructor() {
        this.loaded = false;
        this.loading = false;
        this.loadPromise = null;
        
        // CDN options with fallbacks
        this.cdnOptions = [
            'https://cdn.jsdelivr.net/npm/markdown-it@13.0.1/dist/markdown-it.min.js',
            'https://unpkg.com/markdown-it@13.0.1/dist/markdown-it.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/markdown-it/13.0.1/markdown-it.min.js'
        ];
    }
    
    async loadMarkdownIt() {
        // Return existing promise if already loading
        if (this.loading && this.loadPromise) {
            return this.loadPromise;
        }
        
        // Return immediately if already loaded
        if (this.loaded && typeof markdownit !== 'undefined') {
            return Promise.resolve(true);
        }
        
        this.loading = true;
        
        this.loadPromise = this.tryLoadFromCDNs();
        
        try {
            const result = await this.loadPromise;
            this.loaded = result;
            this.loading = false;
            return result;
        } catch (error) {
            this.loading = false;
            console.warn('Failed to load markdown-it:', error);
            return false;
        }
    }
    
    async tryLoadFromCDNs() {
        for (let i = 0; i < this.cdnOptions.length; i++) {
            const cdnUrl = this.cdnOptions[i];
            
            try {
                console.log(`Attempting to load markdown-it from: ${cdnUrl}`);
                
                const success = await this.loadScriptFromCDN(cdnUrl);
                
                if (success && typeof markdownit !== 'undefined') {
                    console.log(`Successfully loaded markdown-it from: ${cdnUrl}`);
                    return true;
                }
            } catch (error) {
                console.warn(`Failed to load from ${cdnUrl}:`, error);
                continue;
            }
        }
        
        console.warn('All markdown-it CDN sources failed, using fallback renderer');
        return false;
    }
    
    loadScriptFromCDN(url) {
        return new Promise((resolve, reject) => {
            // Check if script already exists
            const existingScript = document.querySelector(`script[src="${url}"]`);
            if (existingScript) {
                resolve(true);
                return;
            }
            
            const script = document.createElement('script');
            script.src = url;
            script.async = true;
            
            const timeout = setTimeout(() => {
                script.remove();
                reject(new Error('Script load timeout'));
            }, 10000); // 10 second timeout
            
            script.onload = () => {
                clearTimeout(timeout);
                resolve(true);
            };
            
            script.onerror = () => {
                clearTimeout(timeout);
                script.remove();
                reject(new Error('Script load error'));
            };
            
            document.head.appendChild(script);
        });
    }
    
    isLoaded() {
        return this.loaded && typeof markdownit !== 'undefined';
    }
    
    isLoading() {
        return this.loading;
    }
}

// Global instance
window.markdownLoader = new MarkdownLoader();

// Auto-load on page ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.markdownLoader.loadMarkdownIt().then(success => {
            if (success) {
                console.log('Markdown-it loaded successfully');
                // Dispatch event for components that need markdown
                document.dispatchEvent(new CustomEvent('markdownLoaded'));
            }
        });
    });
} else {
    // DOM already loaded
    window.markdownLoader.loadMarkdownIt().then(success => {
        if (success) {
            console.log('Markdown-it loaded successfully');
            document.dispatchEvent(new CustomEvent('markdownLoaded'));
        }
    });
}