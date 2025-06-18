// knowledge_base_agent/static/js/chat.js

document.addEventListener('DOMContentLoaded', function() {
    console.log('Chat.js: Initializing chat functionality');
    
    // --- Model Loading ---
    async function fetchAndPopulateModels() {
        try {
            const response = await fetch('/api/chat/models');
            if (!response.ok) {
                throw new Error('Failed to fetch chat models');
            }
            const models = await response.json();
            
            const widgetSelector = document.getElementById('chat-model-selector-widget');
            const pageSelector = document.getElementById('chat-model-selector-page');

            if (widgetSelector) {
                populateSelector(widgetSelector, models);
            }
            if (pageSelector) {
                populateSelector(pageSelector, models);
            }
        } catch (error) {
            console.error('Error fetching chat models:', error);
        }
    }

    function populateSelector(selector, models) {
        selector.innerHTML = '';
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            selector.appendChild(option);
        });
    }

    // --- Core Chat Logic ---
    async function handleChatSubmit(inputId, historyId, typingIndicatorId, selectorId) {
        const chatInput = document.getElementById(inputId);
        const query = chatInput.value.trim();
        if (!query) return;

        const chatHistory = document.getElementById(historyId);
        const typingIndicator = document.getElementById(typingIndicatorId);
        const modelSelector = document.getElementById(selectorId);

        // Add user message to history
        appendMessage(chatHistory, 'user', query);
        chatInput.value = '';
        chatInput.disabled = true;
        if (typingIndicator) typingIndicator.style.display = 'block';

        const selectedModel = modelSelector ? modelSelector.value : null;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: query, model: selectedModel })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            // Display query type if available
            if (data.query_type) {
                console.log(`Query classified as: ${data.query_type}`);
            }
            
            appendMessage(chatHistory, 'assistant', data.response, data.sources, data.context_stats, data.performance_metrics);

        } catch (error) {
            console.error('Error during chat:', error);
            appendMessage(chatHistory, 'assistant', `Sorry, an error occurred: ${error.message}`);
        } finally {
            if (typingIndicator) typingIndicator.style.display = 'none';
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    function appendMessage(history, role, text, sources = [], contextStats = {}, performanceMetrics = {}) {
        if (!history) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        const p = document.createElement('p');
        p.innerHTML = text.replace(/\n/g, '<br>');
        messageDiv.appendChild(p);

        // Add performance metrics for assistant messages
        if (role === 'assistant' && performanceMetrics && Object.keys(performanceMetrics).length > 0) {
            const metricsDiv = document.createElement('div');
            metricsDiv.className = 'chat-performance-metrics';
            
            const metricsToggle = document.createElement('button');
            metricsToggle.className = 'btn btn-outline-secondary btn-sm metrics-toggle';
            metricsToggle.innerHTML = '<i class="bi bi-speedometer2"></i> Performance';
            metricsToggle.style.fontSize = '0.75rem';
            metricsToggle.style.padding = '2px 6px';
            metricsToggle.style.marginTop = '5px';
            
            const metricsContent = document.createElement('div');
            metricsContent.className = 'metrics-content';
            metricsContent.style.display = 'none';
            metricsContent.style.marginTop = '8px';
            metricsContent.style.padding = '8px';
            metricsContent.style.backgroundColor = '#f8f9fa';
            metricsContent.style.borderRadius = '4px';
            metricsContent.style.fontSize = '0.8rem';
            metricsContent.style.border = '1px solid #dee2e6';
            
            // Format performance metrics
            const metrics = [
                `⏱️ Response Time: ${performanceMetrics.response_time_ms}ms (${performanceMetrics.response_time_seconds}s)`,
                `🚀 Speed: ${performanceMetrics.tokens_per_second} tokens/sec`,
                `📊 Input Tokens: ${performanceMetrics.estimated_input_tokens} | Output: ${performanceMetrics.estimated_output_tokens}`,
                `📈 Total Tokens: ${performanceMetrics.estimated_total_tokens}`,
                `🤖 Model: ${performanceMetrics.model}`,
                `📚 Context Sources: ${performanceMetrics.context_length || 0}`
            ];
            
            metricsContent.innerHTML = metrics.map(metric => `<div>${metric}</div>`).join('');
            
            // Toggle functionality
            metricsToggle.addEventListener('click', () => {
                const isVisible = metricsContent.style.display !== 'none';
                metricsContent.style.display = isVisible ? 'none' : 'block';
                metricsToggle.innerHTML = isVisible ? 
                    '<i class="bi bi-speedometer2"></i> Performance' : 
                    '<i class="bi bi-speedometer2-fill"></i> Performance';
            });
            
            metricsDiv.appendChild(metricsToggle);
            metricsDiv.appendChild(metricsContent);
            messageDiv.appendChild(metricsDiv);
        }

        // Enhanced source display with rich metadata
        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'chat-sources';
            
            // Add context stats if available
            if (contextStats && Object.keys(contextStats).length > 0) {
                const statsDiv = document.createElement('div');
                statsDiv.className = 'chat-context-stats';
                statsDiv.innerHTML = `
                    <strong>📊 Context Summary:</strong> 
                    ${contextStats.total_sources || 0} sources 
                    (${contextStats.synthesis_docs || 0} syntheses, 
                    ${contextStats.kb_items || 0} items) 
                    across ${contextStats.categories_covered || 0} categories
                `;
                sourcesDiv.appendChild(statsDiv);
            }
            
            sourcesDiv.innerHTML += '<strong>🔗 Sources:</strong>';
            const sourcesList = document.createElement('div');
            sourcesList.className = 'sources-list';
            
            sources.forEach((source, index) => {
                const sourceItem = document.createElement('div');
                sourceItem.className = 'source-item';
                
                // Create main source link
                const sourceLink = document.createElement('a');
                sourceLink.href = source.url || '#';
                sourceLink.className = 'source-link';
                sourceLink.textContent = source.title || 'Unknown Source';
                
                // Handle click for navigation
                sourceLink.onclick = (e) => {
                    if (source.url && source.url !== '#') {
                        // Navigate to the source page
                        window.location.href = source.url;
                    } else {
                        e.preventDefault();
                        console.log('Source clicked but no URL available:', source);
                    }
                };
                
                // Create metadata display
                const metadata = document.createElement('div');
                metadata.className = 'source-metadata';
                
                let metadataContent = '';
                
                // Document type with emoji
                if (source.doc_type_display) {
                    metadataContent += `<span class="doc-type">${source.doc_type_display}</span>`;
                }
                
                // Category information
                if (source.category || source.subcategory) {
                    const categoryPath = [source.category, source.subcategory].filter(Boolean).join('/');
                    metadataContent += `<span class="category">${categoryPath}</span>`;
                }
                
                // Relevance score
                if (source.score !== undefined && source.score !== null) {
                    const scorePercent = (source.score * 100).toFixed(1);
                    const scoreClass = source.score > 0.8 ? 'high-score' : source.score > 0.6 ? 'med-score' : 'low-score';
                    metadataContent += `<span class="score ${scoreClass}">${scorePercent}% relevant</span>`;
                }
                
                metadata.innerHTML = metadataContent;
                
                // Assemble source item
                sourceItem.appendChild(sourceLink);
                sourceItem.appendChild(metadata);
                sourcesList.appendChild(sourceItem);
            });
            
            sourcesDiv.appendChild(sourcesList);
            messageDiv.appendChild(sourcesDiv);
        }
        
        history.appendChild(messageDiv);
        history.scrollTop = history.scrollHeight;
    }

    // --- Clear Chat Functionality ---
    function clearChatHistory(historyId) {
        const history = document.getElementById(historyId);
        if (!history) return;
        
        // Remove all chat messages except any initial system message
        const messages = history.querySelectorAll('.chat-message');
        messages.forEach(message => {
            // Keep the initial assistant welcome message
            if (message.classList.contains('assistant-message') && 
                message.querySelector('p')?.textContent.includes('Hello! How can I help you')) {
                return;
            }
            message.remove();
        });
        
        console.log('Chat history cleared');
    }

    function setupClearChatButton(context) {
        const suffix = context === 'widget' ? '-widget' : '-page';
        const clearButtonId = `clear-chat${suffix}`;
        const historyId = `chat-history${suffix}`;
        
        const clearButton = document.getElementById(clearButtonId);
        if (clearButton) {
            // Remove any existing event listeners
            const newButton = clearButton.cloneNode(true);
            clearButton.parentNode.replaceChild(newButton, clearButton);
            
            newButton.addEventListener('click', () => {
                if (confirm('Are you sure you want to clear the chat history?')) {
                    clearChatHistory(historyId);
                }
            });
        }
    }

    // --- Chat Initialization ---
    function initializeChat(context) {
        console.log(`Initializing chat for context: ${context}`);
        
        const suffix = context === 'widget' ? '-widget' : '-page';
        const formId = `chat-form${suffix}`;
        const inputId = `chat-input${suffix}`;
        const historyId = `chat-history${suffix}`;
        const typingIndicatorId = `chat-typing-indicator${suffix}`;
        const selectorId = `chat-model-selector${suffix}`;

        const form = document.getElementById(formId);
        const input = document.getElementById(inputId);
        const history = document.getElementById(historyId);

        if (form && input && history) {
            console.log(`Found chat elements for ${context}`);
            
            // Remove existing event listeners by cloning the form
            const newForm = form.cloneNode(true);
            form.parentNode.replaceChild(newForm, form);
            
            // Get the new input element from the cloned form
            const newInput = newForm.querySelector('textarea');
            if (!newInput) {
                console.error(`Failed to find textarea in cloned form for ${context}`);
                return;
            }
            
            console.log(`Setting up event listeners for ${context}`);
            
            // Add submit handler
            newForm.addEventListener('submit', (event) => {
                event.preventDefault();
                console.log(`Form submitted for ${context}`);
                handleChatSubmit(inputId, historyId, typingIndicatorId, selectorId);
            });

            // Setup Enter/Shift+Enter handling on the new input
            newInput.addEventListener('keydown', function(event) {
                if (event.key === 'Enter') {
                    if (event.shiftKey) {
                        // Shift+Enter: Allow new line (default behavior)
                        console.log(`Shift+Enter pressed for ${context}`);
                        return;
                    } else {
                        // Enter without Shift: Submit form
                        console.log(`Enter pressed for ${context}, submitting form`);
                        event.preventDefault();
                        newForm.dispatchEvent(new Event('submit'));
                    }
                }
            });
            
            // Setup clear chat button
            setupClearChatButton(context);
            
            console.log(`Chat initialized successfully for ${context}`);
        } else {
            console.warn(`Chat elements not found for context: ${context}. Form: ${!!form}, Input: ${!!input}, History: ${!!history}`);
        }
    }

    // --- Widget Chat Initialization ---
    initializeChat('widget');
    
    // --- Dynamic Page Chat Initialization ---
    const observer = new MutationObserver((mutationsList) => {
        for (const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                const chatPageContainer = document.querySelector('.chat-page-container');
                if (chatPageContainer && !chatPageContainer.dataset.initialized) {
                    chatPageContainer.dataset.initialized = 'true';
                    console.log('Chat page detected, initializing...');
                    initializeChat('page');
                    fetchAndPopulateModels(); // Refresh models for the page
                    observer.disconnect();
                    break;
                }
            }
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Initial model load
    fetchAndPopulateModels();
});

// --- Global Functions ---
function toggleChat() {
    const chatWidget = document.querySelector('#chat-widget');
    const chatBody = document.querySelector('#chat-widget .chat-widget-body');
    const toggleIcon = document.querySelector('.chat-toggle-icon');
    
    if (!chatWidget || !toggleIcon) {
        console.error('Chat widget or toggle icon not found');
        return;
    }
    
    if (chatWidget.classList.contains('chat-widget-open')) {
        chatWidget.classList.remove('chat-widget-open');
        if (chatBody) chatBody.style.display = 'none';
        toggleIcon.textContent = '+';
        console.log('Chat widget minimized');
    } else {
        chatWidget.classList.add('chat-widget-open');
        if (chatBody) chatBody.style.display = 'flex';
        toggleIcon.textContent = '-';
        console.log('Chat widget opened');
    }
}

// Global function for reinitializing chat (called from index.js)
function reinitializeChat(context = 'page') {
    console.log(`Global reinitializeChat called for context: ${context}`);
    
    const suffix = context === 'widget' ? '-widget' : '-page';
    const formId = `chat-form${suffix}`;
    const inputId = `chat-input${suffix}`;
    const historyId = `chat-history${suffix}`;
    const typingIndicatorId = `chat-typing-indicator${suffix}`;
    const selectorId = `chat-model-selector${suffix}`;

    const form = document.getElementById(formId);
    const input = document.getElementById(inputId);
    const history = document.getElementById(historyId);

    if (form && input && history) {
        // Remove any existing event listeners to prevent duplicates
        const newForm = form.cloneNode(true);
        form.parentNode.replaceChild(newForm, form);
        
        // Get the new input element from the cloned form
        const newInput = newForm.querySelector('textarea');
        if (!newInput) {
            console.error(`Failed to find textarea in cloned form for ${context}`);
            return;
        }
        
        // Add submit handler  
        async function handleSubmit(event) {
            event.preventDefault();
            const query = newInput.value.trim();
            if (!query) return;

            const modelSelector = document.getElementById(selectorId);
            const typingIndicator = document.getElementById(typingIndicatorId);
            const selectedModel = modelSelector ? modelSelector.value : null;

            // Add user message
            appendMessage(history, 'user', query);
            newInput.value = '';
            newInput.disabled = true;
            if (typingIndicator) typingIndicator.style.display = 'block';

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: query, model: selectedModel })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP ${response.status}`);
                }

                const data = await response.json();
                
                // Display query type if available  
                if (data.query_type) {
                    console.log(`Query classified as: ${data.query_type}`);
                }
                
                appendMessage(history, 'assistant', data.response, data.sources, data.context_stats, data.performance_metrics);

            } catch (error) {
                console.error('Chat error:', error);
                appendMessage(history, 'assistant', `Error: ${error.message}`);
            } finally {
                if (typingIndicator) typingIndicator.style.display = 'none';
                newInput.disabled = false;
                newInput.focus();
            }
        }

        function appendMessage(history, role, text, sources = [], contextStats = {}, performanceMetrics = {}) {
            if (!history) return;
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${role}-message`;
            
            const p = document.createElement('p');
            p.innerHTML = text.replace(/\n/g, '<br>');
            messageDiv.appendChild(p);

            // Add performance metrics for assistant messages
            if (role === 'assistant' && performanceMetrics && Object.keys(performanceMetrics).length > 0) {
                const metricsDiv = document.createElement('div');
                metricsDiv.className = 'chat-performance-metrics';
                
                const metricsToggle = document.createElement('button');
                metricsToggle.className = 'btn btn-outline-secondary btn-sm metrics-toggle';
                metricsToggle.innerHTML = '<i class="bi bi-speedometer2"></i> Performance';
                metricsToggle.style.fontSize = '0.75rem';
                metricsToggle.style.padding = '2px 6px';
                metricsToggle.style.marginTop = '5px';
                
                const metricsContent = document.createElement('div');
                metricsContent.className = 'metrics-content';
                metricsContent.style.display = 'none';
                metricsContent.style.marginTop = '8px';
                metricsContent.style.padding = '8px';
                metricsContent.style.backgroundColor = '#f8f9fa';
                metricsContent.style.borderRadius = '4px';
                metricsContent.style.fontSize = '0.8rem';
                metricsContent.style.border = '1px solid #dee2e6';
                
                // Format performance metrics
                const metrics = [
                    `⏱️ Response Time: ${performanceMetrics.response_time_ms}ms (${performanceMetrics.response_time_seconds}s)`,
                    `🚀 Speed: ${performanceMetrics.tokens_per_second} tokens/sec`,
                    `📊 Input Tokens: ${performanceMetrics.estimated_input_tokens} | Output: ${performanceMetrics.estimated_output_tokens}`,
                    `📈 Total Tokens: ${performanceMetrics.estimated_total_tokens}`,
                    `🤖 Model: ${performanceMetrics.model}`,
                    `📚 Context Sources: ${performanceMetrics.context_length || 0}`
                ];
                
                metricsContent.innerHTML = metrics.map(metric => `<div>${metric}</div>`).join('');
                
                // Toggle functionality
                metricsToggle.addEventListener('click', () => {
                    const isVisible = metricsContent.style.display !== 'none';
                    metricsContent.style.display = isVisible ? 'none' : 'block';
                    metricsToggle.innerHTML = isVisible ? 
                        '<i class="bi bi-speedometer2"></i> Performance' : 
                        '<i class="bi bi-speedometer2-fill"></i> Performance';
                });
                
                metricsDiv.appendChild(metricsToggle);
                metricsDiv.appendChild(metricsContent);
                messageDiv.appendChild(metricsDiv);
            }

            // Enhanced source display with rich metadata
            if (sources && sources.length > 0) {
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'chat-sources';
                
                // Add context stats if available
                if (contextStats && Object.keys(contextStats).length > 0) {
                    const statsDiv = document.createElement('div');
                    statsDiv.className = 'chat-context-stats';
                    statsDiv.innerHTML = `
                        <strong>📊 Context Summary:</strong> 
                        ${contextStats.total_sources || 0} sources 
                        (${contextStats.synthesis_docs || 0} syntheses, 
                        ${contextStats.kb_items || 0} items) 
                        across ${contextStats.categories_covered || 0} categories
                    `;
                    sourcesDiv.appendChild(statsDiv);
                }
                
                sourcesDiv.innerHTML += '<strong>🔗 Sources:</strong>';
                const sourcesList = document.createElement('div');
                sourcesList.className = 'sources-list';
                
                sources.forEach((source, index) => {
                    const sourceItem = document.createElement('div');
                    sourceItem.className = 'source-item';
                    
                    // Create main source link
                    const sourceLink = document.createElement('a');
                    sourceLink.href = source.url || '#';
                    sourceLink.className = 'source-link';
                    sourceLink.textContent = source.title || 'Unknown Source';
                    
                    // Handle click for navigation
                    sourceLink.onclick = (e) => {
                        if (source.url && source.url !== '#') {
                            // Navigate to the source page
                            window.location.href = source.url;
                        } else {
                            e.preventDefault();
                            console.log('Source clicked but no URL available:', source);
                        }
                    };
                    
                    // Create metadata display
                    const metadata = document.createElement('div');
                    metadata.className = 'source-metadata';
                    
                    let metadataContent = '';
                    
                    // Document type with emoji
                    if (source.doc_type_display) {
                        metadataContent += `<span class="doc-type">${source.doc_type_display}</span>`;
                    }
                    
                    // Category information
                    if (source.category || source.subcategory) {
                        const categoryPath = [source.category, source.subcategory].filter(Boolean).join('/');
                        metadataContent += `<span class="category">${categoryPath}</span>`;
                    }
                    
                    // Relevance score
                    if (source.score !== undefined && source.score !== null) {
                        const scorePercent = (source.score * 100).toFixed(1);
                        const scoreClass = source.score > 0.8 ? 'high-score' : source.score > 0.6 ? 'med-score' : 'low-score';
                        metadataContent += `<span class="score ${scoreClass}">${scorePercent}% relevant</span>`;
                    }
                    
                    metadata.innerHTML = metadataContent;
                    
                    // Assemble source item
                    sourceItem.appendChild(sourceLink);
                    sourceItem.appendChild(metadata);
                    sourcesList.appendChild(sourceItem);
                });
                
                sourcesDiv.appendChild(sourcesList);
                messageDiv.appendChild(sourcesDiv);
            }
            
            history.appendChild(messageDiv);
            history.scrollTop = history.scrollHeight;
        }
        
        newForm.addEventListener('submit', handleSubmit);

        // Setup Enter/Shift+Enter handling on the new input
        newInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                if (event.shiftKey) {
                    // Shift+Enter: Allow new line (default behavior)
                    return;
                } else {
                    // Enter without Shift: Submit form
                    event.preventDefault();
                    newForm.dispatchEvent(new Event('submit'));
                }
            }
        });
        
        // Setup clear chat button
        const clearButtonId = `clear-chat${suffix}`;
        const clearButton = document.getElementById(clearButtonId);
        if (clearButton) {
            const newButton = clearButton.cloneNode(true);
            clearButton.parentNode.replaceChild(newButton, clearButton);
            
            newButton.addEventListener('click', () => {
                if (confirm('Are you sure you want to clear the chat history?')) {
                    const messages = history.querySelectorAll('.chat-message');
                    messages.forEach(message => {
                        // Keep the initial assistant welcome message
                        if (message.classList.contains('assistant-message') && 
                            message.querySelector('p')?.textContent.includes('Hello! How can I help you')) {
                            return;
                        }
                        message.remove();
                    });
                    console.log('Chat history cleared');
                }
            });
        }
        
        console.log(`Chat reinitialized for ${context}`);
        
        // Load models if selector exists
        const modelSelector = document.getElementById(selectorId);
        if (modelSelector && modelSelector.children.length === 0) {
            loadChatModels(modelSelector);
        }
    }
}

async function loadChatModels(selector) {
    if (!selector) return;
    try {
        const response = await fetch('/api/chat/models');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const models = await response.json();
        
        selector.innerHTML = '';
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            selector.appendChild(option);
        });
    } catch (error) {
        console.error("Failed to load chat models:", error);
        selector.innerHTML = '<option value="">Error loading models</option>';
    }
}

// Expose functions to global scope
window.reinitializeChat = reinitializeChat;
window.toggleChat = toggleChat; 