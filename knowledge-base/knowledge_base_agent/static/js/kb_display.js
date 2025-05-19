document.addEventListener('DOMContentLoaded', function() {
    const mainContent = document.querySelector('.main-content');
    const sidebarLinks = document.querySelectorAll('.sidebar .item-link');

    function updateActiveSidebarLink(itemId) {
        sidebarLinks.forEach(link => {
            if (itemId && link.href.includes(`/item/${itemId}`)) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    function renderKbItemFromJson(data) {
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

    async function loadItem(url, itemId, pushState = true) {
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
                history.pushState({ itemId: data.id }, data.display_title || data.title, url);
            }
            updateActiveSidebarLink(data.id);
        } catch (error) {
            console.error('Failed to load item:', error);
            mainContent.innerHTML = '<p class="text-danger text-center">Failed to load content. Please try navigating again or check the console.</p>';
        }
    }

    sidebarLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            const url = event.currentTarget.href;
            const itemId = url.substring(url.lastIndexOf('/') + 1);
            loadItem(url, itemId);
        });
    });

    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.itemId) {
            const url = `/item/${event.state.itemId}`; // Assuming this URL structure
            loadItem(url, event.state.itemId, false);
        } else if (!event.state && location.pathname === '/') {
            // If popstate leads to root and no specific state, show welcome/default
            if (mainContent) {
                 mainContent.innerHTML = '<div class="card welcome-card"><div class="card-body"><h5 class="card-title">Welcome to the Knowledge Base</h5><p class="card-text">Use the navigation pane on the left to explore categories and items. Click on any item to view its detailed content here.</p></div></div>'; // Simplified default
                 document.title = 'Knowledge Base';
            }
            updateActiveSidebarLink(null);
        }
        // If event.state is null and not on root, it might be initial page load handled by SSR.
        // Or a state not set by our pushState, potentially ignore or decide default action.
    });

    // On initial page load, if it's an item page, ensure sidebar link is active.
    // The content itself is assumed to be server-rendered for direct item URL access.
    if (location.pathname.startsWith('/item/')) {
        const itemId = location.pathname.substring(location.pathname.lastIndexOf('/') + 1);
        if (itemId) {
             updateActiveSidebarLink(itemId);
             // Server should have rendered the content, so Prism would apply if an item was rendered.
             // If Prism.highlightAll() is in <script> in HTML, it should run.
        }
    }
}); 