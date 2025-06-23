function updateActiveSidebarLink(itemId) {
    const sidebarLinks = document.querySelectorAll('.sidebar .item-link');
    sidebarLinks.forEach(link => {
        if (itemId && link.href.includes(`/item/${itemId}`)) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

function renderKbItemFromJson(data) {
    const mainContent = document.querySelector('.main-content');
    if (!mainContent) return;

    let html = '';
    const item = data; 
    const kb_json_data = data.raw_json_content_parsed;

    if (kb_json_data) {
        html += '<article>';
        html += '<header class="mb-4">';
        html += `<h1 class="fw-bold">${kb_json_data.suggested_title || item.display_title || item.title}</h1>`;
        if (kb_json_data.meta_description) {
            html += `<p class="lead text-muted">${kb_json_data.meta_description}</p>`;
        }
        html += '<small class="text-muted">';
        html += `Category: ${item.main_category.replace(/_/g, ' ')} / ${item.sub_category.replace(/_/g, ' ')}<br>`;
        html += `Last Updated: ${item.last_updated ? new Date(item.last_updated).toLocaleDateString('en-CA') : 'N/A'}`;
        if (item.source_url) {
            html += ` | <a href="${item.source_url}" target="_blank">Original Source</a>`;
        }
        html += '</small><hr></header>';

        if (kb_json_data.introduction) {
            html += `<section class="mb-4"><h3>Introduction</h3><p>${kb_json_data.introduction}</p></section>`;
        }

        if (kb_json_data.sections && kb_json_data.sections.length > 0) {
            kb_json_data.sections.forEach(section => {
                html += '<section class="mb-4">';
                html += `<h4>${section.heading}</h4>`;
                if (section.content_paragraphs && section.content_paragraphs.length > 0) {
                    section.content_paragraphs.forEach(p => { html += `<p>${p}</p>`; });
                }
                if (section.code_blocks && section.code_blocks.length > 0) {
                    section.code_blocks.forEach(cb => {
                        if (cb.explanation) html += `<p><em>${cb.explanation}</em></p>`;
                        const codeContent = cb.code ? cb.code.replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
                        html += `<pre><code class="language-${cb.language || 'plaintext'}">${codeContent}</code></pre>`;
                    });
                }
                if (section.lists && section.lists.length > 0) {
                    section.lists.forEach(list_item => {
                        html += list_item.type === 'numbered' ? '<ol>' : '<ul>';
                        list_item.items.forEach(li => { html += `<li>${li}</li>`; });
                        html += list_item.type === 'numbered' ? '</ol>' : '</ul>';
                    });
                }
                if (section.notes_or_tips && section.notes_or_tips.length > 0) {
                    section.notes_or_tips.forEach(note => {
                        html += `<blockquote class="blockquote"><p><small>${note}</small></p></blockquote>`;
                    });
                }
                html += '</section>';
            });
        }

        if (kb_json_data.key_takeaways && kb_json_data.key_takeaways.length > 0) {
            html += '<section class="mb-4"><h3>Key Takeaways</h3><ul>';
            kb_json_data.key_takeaways.forEach(t => { html += `<li>${t}</li>`; });
            html += '</ul></section>';
        }

        if (kb_json_data.conclusion) {
            html += `<section class="mb-4"><h3>Conclusion</h3><p>${kb_json_data.conclusion}</p></section>`;
        }

        if (kb_json_data.external_references && kb_json_data.external_references.length > 0) {
            html += '<section class="mb-4"><h3>External References</h3><ul>';
            kb_json_data.external_references.forEach(ref => {
                html += `<li><a href="${ref.url}" target="_blank">${ref.text}</a></li>`;
            });
            html += '</ul></section>';
        }
        html += '</article>';
    } else if (item.content) { 
        html += `<header class="mb-4"><h1 class="fw-bold">${item.display_title || item.title}</h1></header>`;
        html += `<div>${item.content}</div>`; 
    } else {
        html += `<h1>${item.display_title || item.title}</h1><p class="text-danger">Content not available.</p>`;
    }

    if (data.media_files_for_template && data.media_files_for_template.length > 0) {
        html += '<div class="mt-5"><h4>Associated Media</h4><div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">';
        data.media_files_for_template.forEach(media => {
            html += '<div class="col"><div class="card h-100">';
            if (media.type === 'image') {
                html += `<img src="${media.url}" class="card-img-top" alt="${media.name}" style="max-height: 200px; object-fit: cover;">`;
            } else if (media.type === 'video') {
                html += `<video controls class="card-img-top" style="max-height: 200px;"><source src="${media.url}" type="video/mp4">Your browser does not support the video tag.</video>`;
            }
            html += `<div class="card-body"><p class="card-text"><small>${media.name}</small></p></div></div></div>`;
        });
        html += '</div></div>';
    }
    mainContent.innerHTML = html;
    document.title = (kb_json_data && kb_json_data.suggested_title) ? kb_json_data.suggested_title : (item.display_title || item.title);
    
    if (window.Prism) {
        Prism.highlightAll();
    }
}

async function loadKbItem(url, itemId, pushState = true) {
    const mainContent = document.querySelector('#main-content-area');
    if (!mainContent) {
        console.error('Main content area not found');
        return;
    }
    mainContent.innerHTML = '<div class="text-center p-5"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    try {
        const response = await fetch(`${url}?format=json`, {
            headers: {
                'Accept': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderKbItemFromJson(data);
        if (pushState) {
            history.pushState({ path: url, itemId: data.id }, data.display_title || data.title, url);
        }
        updateActiveSidebarLink(data.id);
        return data; // Return data for promise chaining
    } catch (error) {
        console.error('Failed to load item:', error);
        mainContent.innerHTML = '<p class="text-danger text-center">Failed to load content. Please try navigating again or check the console.</p>';
        throw error; // Propagate error
    }
}

function initializeKbDisplay() {
    // This function is now called by navigation.js when appropriate.
    // The main navigation handler in navigation.js will now be responsible
    // for detecting clicks on .item-link and calling window.loadKbItem.
    console.log("Knowledge Base display system initialized by conductor.");

    // The popstate listener can remain here as it's self-contained state management
    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.itemId) {
            const url = event.state.path || `/item/${event.state.itemId}`;
            loadKbItem(url, event.state.itemId, false);
        }
    });

    // On initial hard-load of an item page, ensure the sidebar link is active.
    if (location.pathname.startsWith('/item/')) {
        const itemId = location.pathname.substring(location.pathname.lastIndexOf('/') + 1);
        if (itemId) {
             updateActiveSidebarLink(itemId);
        }
    }
}

// Expose necessary functions to the global scope
window.loadKbItem = loadKbItem;
window.updateActiveSidebarLink = updateActiveSidebarLink;
window.initializeKbDisplay = initializeKbDisplay;

// No longer initialize on script load; wait for the conductor.
// initializeKbDisplay(); 