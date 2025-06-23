/**
 * navigation.js
 * Handles Single Page Application (SPA) navigation logic.
 * This script acts as the "Conductor" for the application, orchestrating page loads
 * and initializing page-specific ("specialist") JavaScript modules.
 */

/**
 * Initializes the entire SPA navigation system.
 * This function is the main entry point, called once by a global script (index.js).
 */
function initializeSPANavigation() {
    const contentArea = document.getElementById('main-content-area');

    /**
     * Loads page content from the server and injects it into the main content area.
     * @param {string} url - The URL of the page to load.
     * @param {boolean} pushState - Whether to push a new state to the browser's history.
     */
    const loadPage = async (url, pushState = true) => {
        if (!contentArea) {
            console.error("Fatal: #main-content-area not found. SPA navigation disabled.");
            window.location.href = url; // Fallback to traditional navigation
            return;
        }

        // Provide immediate user feedback that navigation is occurring.
        contentArea.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="height: 80vh;">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>`;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const html = await response.text();
            
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContentWrapper = doc.querySelector('.page-content-wrapper');
            const newTitle = doc.querySelector('title')?.textContent || document.title;

            if (newContentWrapper) {
                // Step 1: Replace the DOM content.
                contentArea.innerHTML = newContentWrapper.innerHTML;
                document.title = newTitle;

                // Step 2: Update browser history if required.
                if (pushState) {
                    history.pushState({ path: url }, newTitle, url);
                }

                // Step 3: Update the active link in the sidebar.
                updateActiveLink(url);

                // Step 4: Run the specific initialization script for the new page.
                initializePageScript(url);
            } else {
                throw new Error("Could not find '.page-content-wrapper' in fetched content.");
            }
        } catch (error) {
            console.error('Error loading page content:', error);
            contentArea.innerHTML = `<p class="text-danger p-4">Error loading content. Please try again or refresh the page.</p>`;
        }
    };

    /**
     * Acts as a router to call the correct "specialist" initialization function
     * based on the page's URL.
     * @param {string} pageUrl - The URL of the page that was just loaded.
     */
    function initializePageScript(pageUrl) {
        console.log(`Routing script initialization for: ${pageUrl}`);
        
        if (pageUrl === '/logs' && window.initializeLogsPage) {
            window.initializeLogsPage();
        } else if ((pageUrl === '/agent' || pageUrl === '/') && window.initializeAgentControlPanel) {
            window.initializeAgentControlPanel();
        } else if (pageUrl.startsWith('/kb/') && window.initializeKbDisplay) {
            window.initializeKbDisplay();
        } else if (pageUrl === '/syntheses' && window.initializeSynthesesList) {
            window.initializeSynthesesList();
        } else if (pageUrl.startsWith('/synthesis/') && window.initializeSynthesisDisplay) {
            window.initializeSynthesisDisplay();
        } else if (pageUrl === '/schedule' && window.initializeSchedulePage) {
            window.initializeSchedulePage();
        } else if (pageUrl === '/environment' && window.initializeEnvironmentPage) {
            window.initializeEnvironmentPage();
        } else if (pageUrl === '/chat' && window.initializeChatPage) {
            window.initializeChatPage();
        }
    }

    /**
     * Sets up a global click listener to intercept all navigation link clicks.
     * This uses event delegation for maximum efficiency.
     */
    function setupClickListener() {
        document.body.addEventListener('click', (event) => {
            const link = event.target.closest('a');
            
            // Ensure it's a valid, local, SPA-routable link.
            const isSPALink = link && link.href && link.target !== '_blank' &&
                              new URL(link.href).origin === window.location.origin &&
                              !link.getAttribute('data-bs-toggle') &&
                              link.getAttribute('href') && !link.getAttribute('href').startsWith('#');

            if (isSPALink) {
                event.preventDefault();
                const destinationUrl = new URL(link.href).pathname;
                
                if (destinationUrl !== window.location.pathname) {
                    console.log('Navigating to:', destinationUrl);
                    loadPage(destinationUrl);
                }
            }
        });
    }

    /**
     * Listens for the browser's back and forward buttons.
     */
    function setupHistoryListener() {
        window.addEventListener('popstate', (event) => {
            if (event.state && event.state.path) {
                console.log('Handling popstate for:', event.state.path);
                loadPage(event.state.path, false);
            }
        });
    }

    /**
     * Updates the 'active' class on sidebar navigation links.
     * @param {string} path - The current page path.
     */
    const updateActiveLink = (path) => {
        const sidebar = document.getElementById('sidebar-nav');
        if (!sidebar) return;
        
        const navLinks = sidebar.querySelectorAll('a.nav-link');
        navLinks.forEach(link => {
            const linkPath = new URL(link.href).pathname;
            // Handle the main page being either '/' or '/agent'
            const isActive = (linkPath === path) || (path === '/' && linkPath === '/agent');
            if (isActive) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    };

    // --- Kick-off ---
    
    setupClickListener();
    setupHistoryListener();

    // Store the initial page state in history so the back button works correctly.
    history.replaceState({ path: window.location.pathname }, document.title, window.location.href);
    
    // Set the active link for the initial page load.
    updateActiveLink(window.location.pathname);
    
    // Run the initializer for the very first page loaded from the server.
    initializePageScript(window.location.pathname);
    
    console.log('SPA navigation conductor initialized.');
}

// Expose the main initializer to be called by another script.
window.initializeSPANavigation = initializeSPANavigation; 