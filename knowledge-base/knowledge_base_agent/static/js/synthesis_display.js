function updateActiveSynthesisLink(synthesisId) {
    const allSynthesisLinks = document.querySelectorAll('.sidebar .synthesis-link');
    allSynthesisLinks.forEach(link => {
        if (synthesisId && link.href.includes(`/synthesis/${synthesisId}`)) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

function renderSynthesisFromJson(data) {
    const mainContent = document.querySelector('.main-content');
    if (!mainContent) return;
    
    let html = '';
    const synthesis = data;
    const raw_json_data = data.raw_json_content_parsed;

    html += '<div class="page-content-wrapper">';
    html += '<div class="col-12 p-0">';
    html += '<div class="card">';
    
    // Header
    html += '<div class="card-header">';
    html += '<div class="d-flex align-items-center mb-2">';
    html += '<i class="bi bi-lightbulb-fill text-warning me-2" style="font-size: 1.5rem;"></i>';
    html += '<span class="badge bg-primary me-2">Synthesis Document</span>';
    html += `<h5 class="card-title mb-0">${synthesis.synthesis_title}</h5>`;
    html += '</div>';
    html += '<small class="text-muted">';
    html += `<strong>Category:</strong> ${synthesis.main_category.replace(/_/g, ' ')} / ${synthesis.sub_category.replace(/_/g, ' ')}<br>`;
    html += `<strong>Based on:</strong> ${synthesis.item_count} knowledge base items<br>`;
    if (synthesis.created_at) {
        html += `<strong>Created:</strong> ${new Date(synthesis.created_at).toLocaleDateString('en-CA')} UTC<br>`;
    }
    if (synthesis.last_updated) {
        html += `<strong>Last Updated:</strong> ${new Date(synthesis.last_updated).toLocaleDateString('en-CA')} UTC`;
    }
    html += '</small>';
    html += '</div>';

    // Body
    html += '<div class="card-body">';

    if (raw_json_data) {
        // Executive Summary
        if (raw_json_data.executive_summary) {
            html += '<section class="mb-4">';
            html += '<h4>Executive Summary</h4>';
            html += '<div class="alert alert-info">';
            html += `<p>${raw_json_data.executive_summary}</p>`;
            html += '</div>';
            html += '</section>';
        }

        // Core Concepts
        if (raw_json_data.core_concepts && raw_json_data.core_concepts.length > 0) {
            html += '<section class="mb-4">';
            html += '<h4>Core Concepts</h4>';
            html += '<ul class="list-group list-group-flush">';
            raw_json_data.core_concepts.forEach(concept => {
                html += '<li class="list-group-item">';
                const conceptName = concept.concept || 'Unnamed Concept';
                const conceptDesc = concept.description || 'No description available';
                html += `<strong>${conceptName}</strong>: ${conceptDesc}`;
                html += '</li>';
            });
            html += '</ul>';
            html += '</section>';
        }

        // Key Insights
        if (raw_json_data.key_insights && raw_json_data.key_insights.length > 0) {
            html += '<section class="mb-4">';
            html += '<h4>Key Insights</h4>';
            html += '<div class="row">';
            raw_json_data.key_insights.forEach(insight => {
                html += '<div class="col-md-6 mb-3">';
                html += '<div class="card h-100">';
                html += '<div class="card-body">';
                const insightTitle = insight.title || 'Untitled Insight';
                const insightDesc = insight.description || 'No description available';
                html += `<h6 class="card-title">${insightTitle}</h6>`;
                html += `<p class="card-text">${insightDesc}</p>`;
                if (insight.examples && insight.examples.length > 0) {
                    html += '<h6 class="card-subtitle mb-2 text-muted">Examples:</h6>';
                    html += '<ul class="small">';
                    insight.examples.forEach(example => {
                        html += `<li>${example || 'No example provided'}</li>`;
                    });
                    html += '</ul>';
                }
                html += '</div>';
                html += '</div>';
                html += '</div>';
            });
            html += '</div>';
            html += '</section>';
        }

        // Patterns and Trends
        if (raw_json_data.patterns_and_trends && raw_json_data.patterns_and_trends.length > 0) {
            html += '<section class="mb-4">';
            html += '<h4>Patterns and Trends</h4>';
            html += '<div class="accordion" id="patternsAccordion">';
            raw_json_data.patterns_and_trends.forEach((pattern, index) => {
                const patternTitle = pattern.title || 'Untitled Pattern';
                const patternDesc = pattern.description || 'No description available';
                html += '<div class="accordion-item">';
                html += `<h2 class="accordion-header" id="heading${index + 1}">`;
                html += `<button class="accordion-button${index === 0 ? '' : ' collapsed'}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${index + 1}" aria-expanded="${index === 0 ? 'true' : 'false'}" aria-controls="collapse${index + 1}">`;
                html += `${patternTitle}`;
                html += '</button>';
                html += '</h2>';
                html += `<div id="collapse${index + 1}" class="accordion-collapse collapse${index === 0 ? ' show' : ''}" aria-labelledby="heading${index + 1}" data-bs-parent="#patternsAccordion">`;
                html += '<div class="accordion-body">';
                html += `<p>${patternDesc}</p>`;
                if (pattern.evidence && pattern.evidence.length > 0) {
                    html += '<h6>Evidence:</h6>';
                    html += '<ul>';
                    pattern.evidence.forEach(evidence => {
                        html += `<li>${evidence || 'No evidence provided'}</li>`;
                    });
                    html += '</ul>';
                }
                html += '</div>';
                html += '</div>';
                html += '</div>';
            });
            html += '</div>';
            html += '</section>';
        }

        // Practical Applications
        if (raw_json_data.practical_applications && raw_json_data.practical_applications.length > 0) {
            html += '<section class="mb-4">';
            html += '<h4>Practical Applications</h4>';
            html += '<div class="row">';
            raw_json_data.practical_applications.forEach(application => {
                const appTitle = application.title || 'Untitled Application';
                const appDesc = application.description || 'No description available';
                html += '<div class="col-lg-4 col-md-6 mb-3">';
                html += '<div class="card">';
                html += '<div class="card-body">';
                html += `<h6 class="card-title">${appTitle}</h6>`;
                html += `<p class="card-text small">${appDesc}</p>`;
                if (application.steps && application.steps.length > 0) {
                    html += '<ol class="small">';
                    application.steps.forEach(step => {
                        html += `<li>${step || 'No step description'}</li>`;
                    });
                    html += '</ol>';
                }
                html += '</div>';
                html += '</div>';
                html += '</div>';
            });
            html += '</div>';
            html += '</section>';
        }

        // Recommendations
        if (raw_json_data.recommendations && raw_json_data.recommendations.length > 0) {
            html += '<section class="mb-4">';
            html += '<h4>Recommendations</h4>';
            html += '<div class="alert alert-success">';
            html += '<ul class="mb-0">';
            raw_json_data.recommendations.forEach(recommendation => {
                html += `<li>${recommendation || 'No recommendation provided'}</li>`;
            });
            html += '</ul>';
            html += '</div>';
            html += '</section>';
        }

        // Related Topics
        if (raw_json_data.related_topics && raw_json_data.related_topics.length > 0) {
            html += '<section class="mb-4">';
            html += '<h4>Related Topics</h4>';
            html += '<div class="d-flex flex-wrap gap-2">';
            raw_json_data.related_topics.forEach(topic => {
                html += `<span class="badge bg-secondary">${topic || 'No topic'}</span>`;
            });
            html += '</div>';
            html += '</section>';
        }
    } else if (synthesis.synthesis_content) {
        // Fall back to markdown content
        html += '<div class="synthesis-content">';
        html += synthesis.synthesis_content; // Assume it's already rendered as HTML
        html += '</div>';
    } else {
        html += '<p class="text-danger">Content not available.</p>';
    }

    // Metadata section
    html += '<hr>';
    html += '<section class="metadata-section">';
    html += '<h5>Document Information</h5>';
    html += '<div class="row">';
    html += '<div class="col-md-6">';
    html += `<p><strong>Source Items:</strong> ${synthesis.item_count} knowledge base entries</p>`;
    html += `<p><strong>Category:</strong> ${synthesis.main_category.replace(/_/g, ' ')}</p>`;
    html += `<p><strong>Subcategory:</strong> ${synthesis.sub_category.replace(/_/g, ' ')}</p>`;
    html += '</div>';
    html += '<div class="col-md-6">';
    if (synthesis.created_at) {
        html += `<p><strong>Created:</strong> ${new Date(synthesis.created_at).toLocaleDateString('en-CA')} UTC</p>`;
    }
    if (synthesis.last_updated) {
        html += `<p><strong>Last Updated:</strong> ${new Date(synthesis.last_updated).toLocaleDateString('en-CA')} UTC</p>`;
    }
    if (synthesis.file_path) {
        html += `<p><strong>File:</strong> <code>${synthesis.file_path}</code></p>`;
    }
    html += '</div>';
    html += '</div>';
    html += '</section>';

    html += '</div>'; // card-body
    html += '</div>'; // card
    html += '</div>'; // col-12
    html += '</div>'; // page-content-wrapper

    mainContent.innerHTML = html;
    document.title = synthesis.synthesis_title;
    
    // Reinitialize Bootstrap components if needed
    if (window.bootstrap && typeof window.bootstrap.Collapse !== 'undefined') {
        // Initialize any new accordion elements
        const accordions = document.querySelectorAll('.accordion-button');
        accordions.forEach(button => {
            if (!button.hasAttribute('data-bs-initialized')) {
                button.setAttribute('data-bs-initialized', 'true');
            }
        });
    }
    
    // Reinitialize Prism highlighting
    if (window.Prism) {
        Prism.highlightAll();
    }
}

async function loadSynthesis(url, synthesisId, pushState = true) {
    const mainContent = document.querySelector('#main-content-area');
    if (!mainContent) {
        console.error('Main content area not found');
        return Promise.reject('Main content area not found');
    }
    mainContent.innerHTML = '<div class="text-center p-5"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    
    try {
        const response = await fetch(`${url}?format=json`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderSynthesisFromJson(data);
        if (pushState) {
            history.pushState({ path: url, synthesisId: data.id }, data.synthesis_title, url);
        }
        updateActiveSynthesisLink(data.id);
        return data; // Return data for promise chaining
    } catch (error) {
        console.error('Failed to load synthesis:', error);
        mainContent.innerHTML = '<p class="text-danger text-center">Failed to load content. Please try navigating again.</p>';
        throw error; // Propagate error for the caller to handle
    }
}

function initializeSynthesisSearch() {
    const synthesisSearchInput = document.getElementById('searchSyntheses');
    if (synthesisSearchInput) {
        synthesisSearchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const synthesisItems = document.querySelectorAll('#collapseSyntheses .synthesis-link');
            const synthesisCategories = document.querySelectorAll('#collapseSyntheses > ul > li');

            synthesisItems.forEach(link => {
                const text = link.textContent.toLowerCase();
                const listItem = link.closest('li');
                listItem.style.display = text.includes(searchTerm) ? '' : 'none';
            });

            synthesisCategories.forEach(category => {
                const visibleItems = category.querySelectorAll('.synthesis-link:not([style*="display: none"])').length;
                category.style.display = visibleItems > 0 ? '' : 'none';
            });

            if (searchTerm) {
                const collapsibles = document.querySelectorAll('#collapseSyntheses .collapse');
                collapsibles.forEach(collapse => {
                    if (!collapse.classList.contains('show')) {
                        new bootstrap.Collapse(collapse, { show: true });
                    }
                });
            }
        });
    }
}

function initializeSynthesisDisplay() {
    console.log("Synthesis display system initialized by conductor.");
    initializeSynthesisSearch();

    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.synthesisId) {
            const url = event.state.path || `/synthesis/${event.state.synthesisId}`;
            loadSynthesis(url, event.state.synthesisId, false);
        }
    });

    if (location.pathname.startsWith('/synthesis/')) {
        const synthesisId = location.pathname.substring(location.pathname.lastIndexOf('/') + 1);
        if (synthesisId) {
             updateActiveSynthesisLink(synthesisId);
        }
    }
}

window.loadSynthesis = loadSynthesis;
window.updateActiveSynthesisLink = updateActiveSynthesisLink;
window.initializeSynthesisDisplay = initializeSynthesisDisplay;

// No longer initialize on script load; wait for the conductor.
// initializeSynthesisDisplay(); 