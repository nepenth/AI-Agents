// knowledge_base_agent/static/js/chat.js

document.addEventListener('DOMContentLoaded', function() {
    // This script now handles both the widget and the potential dedicated chat page
    
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
    async function handleChatSubmit(event, inputId, historyId, indicatorId, selectorId) {
        event.preventDefault();
        const chatInput = document.getElementById(inputId);
        const query = chatInput.value.trim();
        if (!query) return;

        const chatHistory = document.getElementById(historyId);
        const typingIndicator = document.getElementById(indicatorId);
        const modelSelector = document.getElementById(selectorId);

        // Add user message to history
        appendMessage(chatHistory, 'user', query);
        chatInput.value = '';
        chatInput.disabled = true;
        typingIndicator.style.display = 'block';

        const selectedModel = modelSelector ? modelSelector.value : null;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query, model: selectedModel })
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const data = await response.json();
            appendMessage(chatHistory, 'assistant', data.response, data.sources);

        } catch (error) {
            console.error('Error during chat:', error);
            appendMessage(chatHistory, 'assistant', `Sorry, an error occurred: ${error.message}`);
        } finally {
            typingIndicator.style.display = 'none';
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    function appendMessage(history, role, text, sources = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        const p = document.createElement('p');
        p.innerHTML = text.replace(/\n/g, '<br>'); // Basic markdown for newlines
        messageDiv.appendChild(p);

        if (sources && sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'chat-sources';
            sourcesDiv.innerHTML = '<strong>Sources:</strong>';
            const ul = document.createElement('ul');
            sources.forEach(source => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.href = `#`; // Can be updated to link to item/synthesis detail
                a.textContent = source.title || source.source;
                a.onclick = (e) => {
                    e.preventDefault();
                    // Assumes a global function `loadItemDetails` exists
                    if (window.loadItemDetails) {
                        window.loadItemDetails(source.type, source.id);
                    }
                };
                li.appendChild(a);
                ul.appendChild(li);
            });
            sourcesDiv.appendChild(ul);
            messageDiv.appendChild(sourcesDiv);
        }
        
        history.appendChild(messageDiv);
        history.scrollTop = history.scrollHeight;
    }

    // --- Event Listeners ---
    function initializeChat(formId, inputId, historyId, indicatorId, selectorId) {
        const chatForm = document.getElementById(formId);
        if (chatForm) {
            chatForm.addEventListener('submit', (event) => handleChatSubmit(event, inputId, historyId, indicatorId, selectorId));
        }
    }

    // Initialize for widget
    initializeChat('chat-form-widget', 'chat-input-widget', 'chat-history-widget', 'chat-typing-indicator-widget', 'chat-model-selector-widget');
    
    // The chat page content is loaded dynamically, so we need to initialize it when it's added to the DOM.
    // We'll use a MutationObserver to watch for the chat page container.
    const observer = new MutationObserver((mutationsList, observer) => {
        for(const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                const chatPageContainer = document.querySelector('.chat-page-container');
                if (chatPageContainer) {
                    initializeChat('chat-form-page', 'chat-input-page', 'chat-history-page', 'chat-typing-indicator-page', 'chat-model-selector-page');
                    fetchAndPopulateModels(); // Also populate models for the new page
                    observer.disconnect(); // Stop observing once found and initialized
                    break;
                }
            }
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Initial load for the widget
    fetchAndPopulateModels();
});

// Global function for toggling chat widget
function toggleChat() {
    const chatWidget = document.querySelector('#chat-widget');
    const toggleIcon = document.querySelector('.chat-toggle-icon');
    
    if (!chatWidget || !toggleIcon) {
        console.error('Chat widget or toggle icon not found');
        return;
    }
    
    if (chatWidget.classList.contains('chat-widget-open')) {
        chatWidget.classList.remove('chat-widget-open');
        toggleIcon.textContent = '+';
        console.log('Chat widget minimized');
    } else {
        chatWidget.classList.add('chat-widget-open');
        toggleIcon.textContent = '-';
        console.log('Chat widget opened');
    }
}

function initializeChat(context = 'page') {
    console.log(`Initializing chat functions for context: ${context}`);

    const isWidget = context === 'widget';
    const suffix = isWidget ? '-widget' : '-page';

    const form = document.getElementById(`chat-form${suffix}`);
    const input = document.getElementById(`chat-input${suffix}`);
    const history = document.getElementById(`chat-history${suffix}`);
    const modelSelector = document.getElementById(`chat-model-selector${suffix}`);
    const typingIndicator = document.getElementById(`chat-typing-indicator${suffix}`);

    // Only load models if a selector exists for the current context
    if (modelSelector) {
        loadChatModels(modelSelector);
    }

    if (form && input && history) {
        form.removeEventListener('submit', handleFormSubmit); // Prevent duplicates
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const selectedModel = modelSelector ? modelSelector.value : null;
            handleFormSubmit(e, input, history, selectedModel, typingIndicator);
        });
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
        selector.innerHTML = '<option value="">Error</option>';
    }
}

async function handleFormSubmit(event, input, history, model, typingIndicator) {
    const userInput = input.value.trim();
    if (!userInput) return;

    addMessage(history, 'user', userInput);
    input.value = '';
    if (typingIndicator) typingIndicator.style.display = 'block';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userInput, model: model }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Unknown server error');
        }

        const data = await response.json();
        addMessage(history, 'assistant', data.response, data.sources);

    } catch (error) {
        addMessage(history, 'assistant', `Error: ${error.message}`);
    } finally {
        if (typingIndicator) typingIndicator.style.display = 'none';
    }
}

function addMessage(history, sender, text, sources = []) {
    if (!history) return;
    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${sender}-message`;

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = '<div class="chat-sources"><strong>Sources:</strong><ul>';
        sources.forEach(source => {
            // Use the navigation link handler for SPA-style navigation
            sourcesHtml += `<li><a href="#" class="nav-link" data-page="item/${source.id}">${source.title}</a> (Score: ${source.score.toFixed(2)})</li>`;
        });
        sourcesHtml += '</ul></div>';
    }

    // Convert markdown-like lists to HTML lists
    let formattedText = text.replace(/\\n/g, '<br>');
    formattedText = formattedText.replace(/- /g, '• ');
    
    messageElement.innerHTML = `<p>${formattedText}</p>${sourcesHtml}`;
    history.appendChild(messageElement);
    history.scrollTop = history.scrollHeight;
}

// Expose functions to the global scope
window.initializeChat = initializeChat;
window.toggleChat = toggleChat;

// Initial call for the chat widget which is always present
document.addEventListener('DOMContentLoaded', () => {
    initializeChat('widget');
}); 