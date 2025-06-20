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
                    console.log('Calling reinitializeDynamicComponents after navigation');
                    // Add a small delay to ensure DOM is fully ready
                    setTimeout(() => {
                        window.reinitializeDynamicComponents();
                    }, 50);
                }

                // Initialize chat functionality if it's the chat page
                if (window.reinitializeChat && document.getElementById('chat-page-container')) {
                    window.reinitializeChat('page');
                }

                // Initialize syntheses page specific scripts
                if (window.initializeSynthesesPage && document.getElementById('synthesis-list')) {
                    window.initializeSynthesesPage();
                }

                // Initialize logs page specific scripts
                if (window.initializeLogsPage && document.getElementById('log-file-select')) {
                    window.initializeLogsPage();
                }

                // Initialize environment manager if it's the environment page
                if (document.querySelector('.environment-manager')) {
                    console.log('Environment page detected, creating EnvironmentManager');
                    // Ensure any existing instance is cleaned up
                    if (window.environmentManager) {
                        delete window.environmentManager;
                    }
                    // Load the environment script if not already loaded
                    if (typeof EnvironmentManager === 'undefined') {
                        const script = document.createElement('script');
                        script.src = '/static/js/environment.js';
                        script.onload = () => {
                            window.environmentManager = new EnvironmentManager();
                        };
                        document.head.appendChild(script);
                    } else {
                        window.environmentManager = new EnvironmentManager();
                    }
                }

                // Initialize schedule manager if it's the schedule page
                if (document.querySelector('.schedule-manager')) {
                    console.log('Schedule page detected, creating ScheduleManager');
                    // Ensure any existing instance is cleaned up
                    if (window.scheduleManager) {
                        delete window.scheduleManager;
                    }
                    // Load the schedule script if not already loaded
                    if (typeof ScheduleManager === 'undefined') {
                        const script = document.createElement('script');
                        script.src = '/static/js/schedule.js';
                        script.onload = () => {
                            window.scheduleManager = new ScheduleManager();
                        };
                        document.head.appendChild(script);
                    } else {
                        window.scheduleManager = new ScheduleManager();
                    }
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
                    
                    // Special handling for synthesis documents
                    if (destinationUrl.startsWith('/synthesis/') && window.loadSynthesis) {
                        const synthesisId = destinationUrl.substring(destinationUrl.lastIndexOf('/') + 1);
                        console.log('Loading synthesis document:', synthesisId);
                        
                        // Show loading indicator
                        contentArea.innerHTML = `
                            <div class="d-flex justify-content-center align-items-center" style="height: 80vh;">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading synthesis...</span>
                                </div>
                            </div>`;
                        
                        window.loadSynthesis(destinationUrl, synthesisId, true)
                            .then(data => {
                                // Update browser history
                                history.pushState({ path: destinationUrl, synthesisId: data.id }, data.synthesis_title, destinationUrl);
                                updateActiveLink(destinationUrl);
                            })
                            .catch(error => {
                                console.error('Failed to load synthesis:', error);
                                contentArea.innerHTML = `<p class="text-danger p-4">Error loading synthesis. Please try again.</p>`;
                            });
                    } else {
                        // Regular navigation for other pages
                        loadContent(destinationUrl);
                    }
                }
            }
        }
    });

    // --- Browser History (Back/Forward Buttons) ---

    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.path) {
            // Special handling for synthesis documents
            if (event.state.path.startsWith('/synthesis/') && window.loadSynthesis) {
                const synthesisId = event.state.synthesisId || event.state.path.substring(event.state.path.lastIndexOf('/') + 1);
                window.loadSynthesis(event.state.path, synthesisId, false)
                    .then(() => {
                        updateActiveLink(event.state.path);
                    })
                    .catch(error => {
                        console.error('Failed to load synthesis on popstate:', error);
                        contentArea.innerHTML = `<p class="text-danger p-4">Error loading synthesis. Please try again.</p>`;
                    });
            } else {
                // Load content without pushing a new state to history
                loadContent(event.state.path, false);
            }
        } else {
            // Handle cases where state is null (e.g., initial page load)
            const currentPath = location.pathname;
            if (currentPath.startsWith('/synthesis/') && window.loadSynthesis) {
                const synthesisId = currentPath.substring(currentPath.lastIndexOf('/') + 1);
                window.loadSynthesis(currentPath, synthesisId, false)
                    .then(() => {
                        updateActiveLink(currentPath);
                    })
                    .catch(error => {
                        console.error('Failed to load synthesis on initial load:', error);
                    });
            } else {
                loadContent(currentPath, false);
            }
        }
    });

    // --- Helper Functions ---

    const reinitializeDynamicScripts = () => {
        console.log("Re-initializing scripts for new content...");
        
        // Call the component re-initializer from index.js
        if (window.reinitializeDynamicComponents) {
            window.reinitializeDynamicComponents();
        }

        // Initialize environment manager if it's the environment page
        if (document.querySelector('.environment-manager')) {
            console.log('Environment page detected, creating EnvironmentManager');
            if (window.environmentManager) {
                delete window.environmentManager;
            }
            if (typeof EnvironmentManager === 'undefined') {
                const script = document.createElement('script');
                script.src = '/static/js/environment.js';
                script.onload = () => {
                    window.environmentManager = new EnvironmentManager();
                };
                document.head.appendChild(script);
            } else {
                window.environmentManager = new EnvironmentManager();
            }
        }

        // Initialize schedule manager if it's the schedule page
        if (document.querySelector('.schedule-manager')) {
            console.log('Schedule page detected, creating ScheduleManager');
            if (window.scheduleManager) {
                delete window.scheduleManager;
            }
            if (typeof ScheduleManager === 'undefined') {
                const script = document.createElement('script');
                script.src = '/static/js/schedule.js';
                script.onload = () => {
                    window.scheduleManager = new ScheduleManager();
                };
                document.head.appendChild(script);
            } else {
                window.scheduleManager = new ScheduleManager();
            }
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
        const synthesisLinks = document.querySelectorAll('.sidebar .synthesis-link');
        const itemLinks = document.querySelectorAll('.sidebar .item-link');
        
        // Clear all active states first
        navLinks.forEach(link => link.classList.remove('active'));
        synthesisLinks.forEach(link => link.classList.remove('active'));
        itemLinks.forEach(link => link.classList.remove('active'));
        
        // Handle synthesis links
        if (path.startsWith('/synthesis/')) {
            synthesisLinks.forEach(link => {
                if (link.href) {
                    const linkPath = new URL(link.href).pathname;
                    if (linkPath === path) {
                        link.classList.add('active');
                    }
                }
            });
            // Update synthesis link active state using the global function if available
            if (window.updateActiveSynthesisLink) {
                const synthesisId = path.substring(path.lastIndexOf('/') + 1);
                window.updateActiveSynthesisLink(synthesisId);
            }
        }
        // Handle knowledge base item links
        else if (path.startsWith('/item/')) {
            itemLinks.forEach(link => {
                if (link.href) {
                    const linkPath = new URL(link.href).pathname;
                    if (linkPath === path) {
                        link.classList.add('active');
                    }
                }
            });
        }
        // Handle regular navigation links
        else {
            navLinks.forEach(link => {
                if (link.href) {
                    const linkPath = new URL(link.href).pathname;
                    if (linkPath === path || (path === '/' && linkPath === '/agent_control_panel')) {
                        link.classList.add('active');
                    }
                }
            });
        }
    };

    // --- Initial State ---
    
    // Store the initial state in history
    history.replaceState({ path: window.location.pathname }, document.title, window.location.href);
    
    // Set the initial active link
    updateActiveLink(window.location.pathname);
    
    console.log('SPA navigation initialized.');
}); 