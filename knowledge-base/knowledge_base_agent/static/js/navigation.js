/**
 * navigation.js
 * Handles Single Page Application (SPA) navigation logic.
 */

document.addEventListener('DOMContentLoaded', () => {
    const contentArea = document.getElementById('main-content-area');
    const sidebar = document.getElementById('sidebar-nav');

    // --- Core Navigation Logic ---

    const loadContent = async (url, pushState = true) => {
        if (!contentArea) {
            console.error("Fatal: #main-content-area not found. SPA navigation disabled.");
            window.location.href = url; // Fallback to traditional navigation
            return;
        }

        // Show a loading indicator
        contentArea.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="height: 80vh;">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const html = await response.text();
            
            // Use DOMParser to avoid issues with script tags and to easily find content
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Find the new content within the fetched HTML
            const newContentWrapper = doc.querySelector('.page-content-wrapper');
            const newTitle = doc.querySelector('title')?.textContent || document.title;
            
            if (newContentWrapper) {
                // Replace the content
                contentArea.innerHTML = newContentWrapper.innerHTML;
                
                // Update the page title
                document.title = newTitle;

                // Update browser history
                if (pushState) {
                    history.pushState({ path: url }, newTitle, url);
                }

                // Re-initialize dynamic components like chat and GPU stats
                if (window.reinitializeDynamicComponents) {
                    window.reinitializeDynamicComponents();
                }

                // Initialize chat page specific scripts
                if (window.initializeChat && document.getElementById('chat-page-container')) {
                    window.initializeChat('page');
                }

                // Initialize syntheses page specific scripts
                if (window.initializeSynthesesPage && document.getElementById('synthesis-list')) {
                    window.initializeSynthesesPage();
                }

                // Initialize logs page specific scripts
                if (window.initializeLogsPage && document.getElementById('log-file-select')) {
                    window.initializeLogsPage();
                }

                // Re-run Prism highlighting if it's used on the loaded page
                if (window.Prism) {
                    Prism.highlightAll();
                }
                
                // Update active link in the sidebar
                updateActiveLink(url);

            } else {
                // If wrapper isn't found, maybe the page is just a content fragment.
                // Or it's a full page without the wrapper. We'll inject its body.
                console.warn("'.page-content-wrapper' not found in fetched HTML. Falling back to body content.");
                contentArea.innerHTML = doc.body.innerHTML;
                document.title = newTitle;
                if (pushState) {
                    history.pushState({ path: url }, newTitle, url);
                }
                reinitializeDynamicScripts();
                updateActiveLink(url);
            }
        } catch (error) {
            console.error('Error loading page content:', error);
            contentArea.innerHTML = `<p class="text-danger p-4">Error loading content. Please try again.</p>`;
        }
    };

    // --- Event Delegation for Navigation ---

    // Listen for clicks on the body to handle all current and future links
    document.body.addEventListener('click', (event) => {
        // Find the closest ancestor which is a link
        const link = event.target.closest('a');
        
        // Check if it's a valid, local navigation link
        if (link && link.href && link.target !== '_blank' && new URL(link.href).origin === window.location.origin) {
            // Check if it's a link that should be handled by the SPA router
            // This excludes collapse toggles, Bootstrap modals, and hash links
            if (!link.getAttribute('data-bs-toggle') && 
                !link.getAttribute('data-bs-target') &&
                !link.href.includes('#collapse') && 
                !link.href.endsWith('#') &&
                link.getAttribute('href') !== '#') {
                
                event.preventDefault(); // Prevent default link behavior
                const destinationUrl = link.getAttribute('href');
                if (destinationUrl && destinationUrl !== window.location.pathname) {
                    console.log('Navigating to:', destinationUrl);
                    loadContent(destinationUrl);
                }
            }
        }
    });

    // --- Browser History (Back/Forward Buttons) ---

    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.path) {
            // Load content without pushing a new state to history
            loadContent(event.state.path, false);
        } else {
            // Handle cases where state is null (e.g., initial page load)
            loadContent(location.pathname, false);
        }
    });

    // --- Helper Functions ---

    const reinitializeDynamicScripts = () => {
        console.log("Re-initializing scripts for new content...");
        
        // Call the component re-initializer from index.js
        if (window.reinitializeDynamicComponents) {
            window.reinitializeDynamicComponents();
        }

        // Re-run Prism highlighting if it's used on the loaded page
        if (window.Prism) {
            Prism.highlightAll();
        }

        // The agent control panel scripts from index.js are tied to elements that are
        // loaded with the page, so they should re-attach if we navigate back to the agent page.
        // We might need a function to re-run event listener attachments if they are lost.
        // For now, let's assume the core `index.js` handles its own elements.
    };

    const updateActiveLink = (path) => {
        if (!sidebar) return;
        // Update nav links in the sidebar
        const navLinks = sidebar.querySelectorAll('a.nav-link');
        
        navLinks.forEach(link => {
            if (link.href) {
                const linkPath = new URL(link.href).pathname;
                if (linkPath === path || (path === '/' && linkPath === '/agent_control_panel')) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            }
        });
    };

    // --- Initial State ---
    
    // Store the initial state in history
    history.replaceState({ path: window.location.pathname }, document.title, window.location.href);
    
    // Set the initial active link
    updateActiveLink(window.location.pathname);
    
    console.log('SPA navigation initialized.');
}); 