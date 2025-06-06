function toggleDarkMode() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

document.addEventListener('DOMContentLoaded', function() {
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        document.documentElement.setAttribute('data-bs-theme', storedTheme);
    }
    // The button event listener will be in index.js as it contains the button
});

// Function to load content into the main area via AJAX
function loadMainContent(url, targetSelector = '.main-content') {
    console.log(`Loading content from: ${url}`);
    $.ajax({
        url: url,
        type: 'GET',
        success: function(data) {
            // Extract the target content and sidebar from the response
            var newContent = $(data).find(targetSelector);
            var newSidebar = $(data).find('.sidebar'); // Assume sidebar update is desired

            if (newContent.length) {
                $(targetSelector).html(newContent.html());
                 if (newSidebar.length) {
                     $('.sidebar').html(newSidebar.html()); // Update sidebar too
                 }
                 // Reinitialize tooltips if present in the new content
                 if ($(targetSelector).find('[data-bs-toggle="tooltip"]').length > 0) {
                    console.log("Reinitializing tooltips");
                    $(targetSelector).find('[data-bs-toggle="tooltip"]').tooltip();
                 }
                 // If loading the logs page, potentially initialize its specific JS
                 if (url === '/logs') {
                     // The JS is embedded in logs.html, so it should run automatically.
                     // If it were separate, you'd call an init function here.
                     console.log("Logs page loaded, specific JS should execute.");
                 }

            } else {
                $(targetSelector).html('<div class="alert alert-warning">Content could not be loaded properly. Response might be missing the target selector.</div>');
                 console.error(`Target selector "${targetSelector}" not found in response from ${url}`);
            }
             // Update browser history (optional, but good for UX)
            try {
                 window.history.pushState({path: url}, '', url);
            } catch(e) { console.warn("history.pushState not supported or failed.")}

        },
        error: function(xhr, status, error) {
            $(targetSelector).html(`<div class="alert alert-danger">Error loading content from ${url}: ${error}</div>`);
            console.error(`AJAX error loading ${url}: ${status} - ${error}`);
        }
    });
}

// === Event Listeners using Delegation ===
$(document).ready(function() {

    // Initialize dark mode on page load
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        const header = document.querySelector('.header');
        if (header) {
            header.classList.add('dark-mode');
        }
    }
    // Initial tooltip setup for static elements
    $('[data-bs-toggle="tooltip"]').tooltip();


    // Delegate click events for ALL sidebar navigation links
    $('body').on('click', '.sidebar .list-group-item-action', function(event) {
        // Exclude collapse toggles from AJAX loading
        if ($(this).data('bs-toggle') === 'collapse') {
            return; // Let Bootstrap handle collapse
        }

        event.preventDefault(); // Prevent default link navigation
        const targetUrl = $(this).attr('href');

        if (targetUrl && targetUrl !== '#') {
             // Special handling for individual item links if needed, but /item/id should work
             if (targetUrl.startsWith('/item/')) {
                 loadMainContent(targetUrl);
             } else if (targetUrl === '/') {
                 loadMainContent('/'); // Load agent controls
             } else if (targetUrl === '/knowledge_base') {
                  loadMainContent('/knowledge_base'); // Load KB main page
             } else if (targetUrl === '/logs') {
                  loadMainContent('/logs'); // Load Logs page
             } else if (targetUrl === '/syntheses') {
                  loadMainContent('/syntheses'); // Load Syntheses list page
             } else if (targetUrl.startsWith('/synthesis/')) {
                  loadMainContent(targetUrl); // Load specific synthesis page
             } else {
                  console.warn(`Unhandled sidebar link clicked: ${targetUrl}`);
             }
             // Optionally remove 'active' class from all siblings and add to clicked one
             $('.sidebar .list-group-item-action.active').removeClass('active');
             $(this).addClass('active');
        } else {
            console.log("Sidebar link without valid href clicked or handled by collapse.");
        }
    });

    // --- Delegate keyup events for search input ---
    // Debounce search input to avoid excessive requests
    let searchTimeout;
    $('body').on('keyup', '#searchKB', function() {
        clearTimeout(searchTimeout);
        const query = $(this).val().trim();

        if (query.length === 0) {
            // Load default KB view if search is cleared
            loadMainContent('/knowledge_base');
            return;
        }

        if (query.length >= 3) {
            searchTimeout = setTimeout(() => {
                console.log('Searching AJAX for: ' + query);
                 // Load search results into the main content area
                 // The search route ('/search') should render a template that includes the '.main-content' div
                 loadMainContent(`/search?q=${encodeURIComponent(query)}`);
            }, 300); // 300ms delay
        }
    });

    // Handle browser back/forward navigation
    $(window).on('popstate', function(event) {
        if (event.originalEvent.state && event.originalEvent.state.path) {
             console.log("Popstate event: loading ", event.originalEvent.state.path);
             // Reload content based on the state path without adding a new history entry
             loadMainContent(event.originalEvent.state.path);
        } else {
            // Handle initial page load or cases where state is null
            console.log("Popstate event with no state or path, potentially initial load.");
            // Optionally load the default view or based on current URL
             loadMainContent(window.location.pathname || '/');
        }
    });


});