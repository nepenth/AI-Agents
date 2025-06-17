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
    async function handleChatSubmit(formId, inputId, historyId, typingIndicatorId, selectorId) {
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
            appendMessage(chatHistory, 'assistant', data.response, data.sources);

        } catch (error) {
            console.error('Error during chat:', error);
            appendMessage(chatHistory, 'assistant', `Sorry, an error occurred: ${error.message}`);
        } finally {
            if (typingIndicator) typingIndicator.style.display = 'none';
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    function appendMessage(history, role, text, sources = []) {
        if (!history) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        const p = document.createElement('p');
        p.innerHTML = text.replace(/\n/g, '<br>');
        messageDiv.appendChild(p);

        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'chat-sources';
            sourcesDiv.innerHTML = '<strong>Sources:</strong>';
            const ul = document.createElement('ul');
            sources.forEach(source => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.href = `#`; 
                a.textContent = source.title || source.source;
                a.onclick = (e) => {
                    e.preventDefault();
                    // Navigation to source could be implemented here
                    console.log('Source clicked:', source);
                };
                
                // Add score if available
                if (source.score !== undefined) {
                    li.appendChild(a);
                    li.appendChild(document.createTextNode(` (Score: ${source.score.toFixed(2)})`));
                } else {
                    li.appendChild(a);
                }
                ul.appendChild(li);
            });
            sourcesDiv.appendChild(ul);
            messageDiv.appendChild(sourcesDiv);
        }
        
        history.appendChild(messageDiv);
        history.scrollTop = history.scrollHeight;
    }

    // --- Enhanced Textarea Handling ---
    function setupTextareaEnterHandling(textareaId, formId) {
        const textarea = document.getElementById(textareaId);
        const form = document.getElementById(formId);
        
        if (!textarea || !form) return;

        textarea.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                if (event.shiftKey) {
                    // Shift+Enter: Allow new line (default behavior)
                    return;
                } else {
                    // Enter without Shift: Submit form
                    event.preventDefault();
                    form.dispatchEvent(new Event('submit'));
                }
            }
        });
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
            // Remove any existing event listeners to prevent duplicates
            const newForm = form.cloneNode(true);
            form.parentNode.replaceChild(newForm, form);
            
            // Add submit handler
            newForm.addEventListener('submit', (event) => {
                event.preventDefault();
                handleChatSubmit(formId, inputId, historyId, typingIndicatorId, selectorId);
            });

            // Setup Enter/Shift+Enter handling
            setupTextareaEnterHandling(inputId, formId);
            
            // Setup clear chat button
            setupClearChatButton(context);
            
            console.log(`Chat initialized for ${context}`);
        } else {
            console.warn(`Chat elements not found for context: ${context}`);
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
function initializeChat(context = 'page') {
    console.log(`Global initializeChat called for context: ${context}`);
    
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
        
        // Add submit handler  
        async function handleSubmit(event) {
            event.preventDefault();
            const query = input.value.trim();
            if (!query) return;

            const modelSelector = document.getElementById(selectorId);
            const typingIndicator = document.getElementById(typingIndicatorId);
            const selectedModel = modelSelector ? modelSelector.value : null;

            // Add user message
            appendMessage(history, 'user', query);
            input.value = '';
            input.disabled = true;
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
                appendMessage(history, 'assistant', data.response, data.sources);

            } catch (error) {
                console.error('Chat error:', error);
                appendMessage(history, 'assistant', `Error: ${error.message}`);
            } finally {
                if (typingIndicator) typingIndicator.style.display = 'none';
                input.disabled = false;
                input.focus();
            }
        }

        function appendMessage(history, role, text, sources = []) {
            if (!history) return;
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${role}-message`;
            
            const p = document.createElement('p');
            p.innerHTML = text.replace(/\n/g, '<br>');
            messageDiv.appendChild(p);

            if (sources && sources.length > 0) {
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'chat-sources';
                sourcesDiv.innerHTML = '<strong>Sources:</strong>';
                const ul = document.createElement('ul');
                sources.forEach(source => {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    a.href = `#`; 
                    a.textContent = source.title || source.source;
                    a.onclick = (e) => {
                        e.preventDefault();
                        console.log('Source clicked:', source);
                    };
                    
                    if (source.score !== undefined) {
                        li.appendChild(a);
                        li.appendChild(document.createTextNode(` (Score: ${source.score.toFixed(2)})`));
                    } else {
                        li.appendChild(a);
                    }
                    ul.appendChild(li);
                });
                sourcesDiv.appendChild(ul);
                messageDiv.appendChild(sourcesDiv);
            }
            
            history.appendChild(messageDiv);
            history.scrollTop = history.scrollHeight;
        }
        
        newForm.addEventListener('submit', handleSubmit);

        // Setup Enter/Shift+Enter handling
        const newInput = document.getElementById(inputId);
        if (newInput) {
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
        }
        
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
window.initializeChat = initializeChat;
window.toggleChat = toggleChat; 