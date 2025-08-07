/**
 * Enhanced Message Renderer - Modern AI Chat with Markdown Support
 * 
 * Features:
 * - Full markdown rendering with syntax highlighting
 * - Improved typography and spacing
 * - Better source attribution formatting
 * - Code block syntax highlighting
 * - Table rendering
 * - Link processing and security
 * - Performance metrics display
 * - Copy functionality for code blocks
 */
class EnhancedMessageRenderer extends BaseManager {
    constructor(chatManager, options = {}) {
        super({
            enableLogging: true,
            componentName: 'EnhancedMessageRenderer',
            ...options
        });
        
        this.chatManager = chatManager;
        
        // Markdown configuration
        this.markdownConfig = {
            breaks: true,
            linkify: true,
            typographer: true,
            highlight: this.highlightCode.bind(this)
        };
        
        // Initialize markdown parser if available
        this.initializeMarkdownParser();
        
        // Source formatting templates
        this.sourceTemplates = {
            kb_item: '📄',
            synthesis: '📋',
            document: '📃',
            default: '📄'
        };
    }
    
    async initializeElements() {
        // No specific elements needed for renderer
    }
    
    initializeMarkdownParser() {
        // Check if markdown-it is available
        if (typeof markdownit !== 'undefined') {
            this.md = markdownit({
                html: false, // Disable HTML for security
                breaks: true,
                linkify: true,
                typographer: true,
                highlight: this.highlightCode.bind(this)
            });
            
            this.log('Markdown parser initialized with syntax highlighting');
        } else {
            this.logWarn('markdown-it not available, using fallback renderer');
            this.md = null;
        }
    }
    
    highlightCode(str, lang) {
        // Simple syntax highlighting for common languages
        if (!lang) return this.escapeHtml(str);
        
        const keywords = {
            javascript: ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'return', 'class', 'async', 'await'],
            python: ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'return', 'import', 'from', 'try', 'except'],
            bash: ['echo', 'cd', 'ls', 'mkdir', 'rm', 'cp', 'mv', 'grep', 'find', 'chmod', 'sudo'],
            sql: ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'],
            css: ['color', 'background', 'margin', 'padding', 'border', 'display', 'position', 'flex'],
            html: ['div', 'span', 'p', 'h1', 'h2', 'h3', 'a', 'img', 'ul', 'li', 'table']
        };
        
        let highlighted = this.escapeHtml(str);
        
        if (keywords[lang.toLowerCase()]) {
            keywords[lang.toLowerCase()].forEach(keyword => {
                const regex = new RegExp(`\\b${keyword}\\b`, 'g');
                highlighted = highlighted.replace(regex, `<span class="code-keyword">${keyword}</span>`);
            });
        }
        
        // Highlight strings
        highlighted = highlighted.replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g, '<span class="code-string">$1$2$1</span>');
        
        // Highlight comments
        if (lang === 'javascript' || lang === 'css') {
            highlighted = highlighted.replace(/(\/\/.*$)/gm, '<span class="code-comment">$1</span>');
            highlighted = highlighted.replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="code-comment">$1</span>');
        } else if (lang === 'python' || lang === 'bash') {
            highlighted = highlighted.replace(/(#.*$)/gm, '<span class="code-comment">$1</span>');
        }
        
        return highlighted;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    createMessageHTML(message, readOnly = false) {
        const isUser = message.role === 'user';
        const timestamp = new Date(message.created_at || Date.now()).toLocaleTimeString();
        
        // Process and format content
        let content = this.processMessageContent(message.content);
        
        // Add performance metrics for assistant messages
        let performanceHTML = '';
        let sourcesHTML = '';
        
        if (!isUser) {
            if (message.performance_metrics) {
                performanceHTML = this.createEnhancedPerformanceMetricsHTML(message.performance_metrics);
            }
            
            if (message.sources && message.sources.length > 0) {
                sourcesHTML = this.createEnhancedSourcesHTML(message.sources);
            }
        }
        
        return `
            <div class="message enhanced-message ${isUser ? 'user-message' : 'assistant-message'} ${readOnly ? 'read-only' : ''}" 
                 data-message-id="${message.id || Date.now()}">
                <div class="message-avatar">
                    <div class="avatar-icon ${isUser ? 'user' : 'assistant'}">
                        <i class="fas fa-${isUser ? 'user' : 'robot'}"></i>
                    </div>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <span class="message-sender">${isUser ? 'You' : 'AI Assistant'}</span>
                        <span class="message-timestamp">${timestamp}</span>
                        ${!readOnly ? this.createMessageHeaderActions(message) : ''}
                    </div>
                    <div class="message-text enhanced-content">${content}</div>
                    ${sourcesHTML}
                    ${performanceHTML}
                    ${!readOnly ? this.createEnhancedMessageActions(message) : ''}
                </div>
            </div>
        `;
    }
    
    processMessageContent(content) {
        if (!content) return '';
        
        // First, clean up common formatting issues
        content = this.cleanupContent(content);
        
        // Process with markdown if available
        if (this.md) {
            content = this.md.render(content);
        } else {
            // Fallback processing
            content = this.processMarkdownFallback(content);
        }
        
        // Post-process for additional enhancements
        content = this.postProcessContent(content);
        
        return content;
    }
    
    cleanupContent(content) {
        // Remove excessive spacing and line breaks
        content = content.replace(/\n{3,}/g, '\n\n');
        
        // Fix common formatting issues from AI responses
        content = content.replace(/^---\s*$/gm, ''); // Remove standalone separators
        content = content.replace(/^\s*\*\*([^*]+)\*\*\s*$/gm, '## $1'); // Convert bold headers to h2
        content = content.replace(/^\s*✅\s*\*\*([^*]+)\*\*\s*/gm, '### ✅ $1\n'); // Convert checkmark headers
        content = content.replace(/^\s*❗\s*\*\*([^*]+)\*\*\s*/gm, '### ❗ $1\n'); // Convert warning headers
        content = content.replace(/^\s*🔍\s*\*\*([^*]+)\*\*\s*/gm, '### 🔍 $1\n'); // Convert search headers
        content = content.replace(/^\s*📌\s*\*\*([^*]+)\*\*\s*/gm, '### 📌 $1\n'); // Convert pin headers
        
        // Improve table formatting
        content = content.replace(/\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|/g, '| $1 | $2 | $3 |');
        
        // Fix source references
        content = content.replace(/\[📄\s*([^\]]+)\]/g, '[📄 $1]');
        content = content.replace(/\[📋\s*([^\]]+)\]/g, '[📋 $1]');
        
        return content.trim();
    }
    
    processMarkdownFallback(content) {
        // Basic markdown processing for when markdown-it isn't available
        
        // Headers
        content = content.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        content = content.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        content = content.replace(/^# (.*$)/gm, '<h1>$1</h1>');
        
        // Bold and italic
        content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        
        // Code blocks
        content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            const highlighted = this.highlightCode(code.trim(), lang);
            return `<div class="code-block-container">
                <div class="code-block-header">
                    <span class="code-language">${lang || 'text'}</span>
                    <button class="code-copy-btn" data-code="${this.escapeHtml(code.trim())}" title="Copy code">
                        <i class="fas fa-copy"></i>
                    </button>
                </div>
                <pre class="code-block"><code class="language-${lang || 'text'}">${highlighted}</code></pre>
            </div>`;
        });
        
        // Inline code
        content = content.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
        
        // Lists
        content = content.replace(/^\s*[-*+]\s+(.+)$/gm, '<li>$1</li>');
        content = content.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        
        // Numbered lists
        content = content.replace(/^\s*\d+\.\s+(.+)$/gm, '<li>$1</li>');
        
        // Links
        content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        
        // Line breaks
        content = content.replace(/\n\n/g, '</p><p>');
        content = '<p>' + content + '</p>';
        
        // Clean up empty paragraphs
        content = content.replace(/<p><\/p>/g, '');
        
        return content;
    }
    
    postProcessContent(content) {
        // Process knowledge base references
        content = content.replace(/\[📄\s*([^\]]+)\]/g, 
            '<span class="kb-reference kb-item" data-kb-item="$1" title="Knowledge Base Item">📄 $1</span>');
        content = content.replace(/\[📋\s*([^\]]+)\]/g, 
            '<span class="kb-reference synthesis-doc" data-synthesis="$1" title="Synthesis Document">📋 $1</span>');
        
        // Enhance external links
        content = content.replace(/<a href="(https?:\/\/[^"]+)"([^>]*)>([^<]+)<\/a>/g, 
            '<a href="$1"$2 class="external-link"><i class="fas fa-external-link-alt"></i> $3</a>');
        
        // Add copy buttons to code blocks if not already present
        content = content.replace(/<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
            if (match.includes('code-copy-btn')) return match; // Already has copy button
            
            const plainCode = code.replace(/<[^>]*>/g, ''); // Strip HTML tags for copying
            return `<div class="code-block-container">
                <div class="code-block-header">
                    <span class="code-language">code</span>
                    <button class="code-copy-btn" data-code="${this.escapeHtml(plainCode)}" title="Copy code">
                        <i class="fas fa-copy"></i>
                    </button>
                </div>
                <pre><code${attrs}>${code}</code></pre>
            </div>`;
        });
        
        return content;
    }
    
    createEnhancedPerformanceMetricsHTML(metrics) {
        const responseTime = metrics.response_time_ms || metrics.response_time || 0;
        const tokensPerSecond = metrics.tokens_per_second || 0;
        const totalTokens = metrics.estimated_total_tokens || metrics.total_tokens || 0;
        const inputTokens = metrics.estimated_input_tokens || metrics.input_tokens || 0;
        const outputTokens = metrics.estimated_output_tokens || metrics.output_tokens || 0;
        
        return `
            <div class="message-performance enhanced-performance">
                <button class="performance-toggle" title="View Performance Metrics">
                    <i class="fas fa-chart-bar"></i>
                    <span class="response-time">${this.chatManager.durationFormatter.format(responseTime)}</span>
                    <span class="tokens-info">${totalTokens} tokens</span>
                    ${tokensPerSecond > 0 ? `<span class="tokens-per-sec">${tokensPerSecond.toFixed(1)} t/s</span>` : ''}
                </button>
                <div class="performance-details hidden">
                    <div class="metrics-grid enhanced-metrics">
                        <div class="metric-card">
                            <div class="metric-icon"><i class="fas fa-clock"></i></div>
                            <div class="metric-content">
                                <div class="metric-label">Response Time</div>
                                <div class="metric-value">${this.chatManager.durationFormatter.format(responseTime)}</div>
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-icon"><i class="fas fa-tachometer-alt"></i></div>
                            <div class="metric-content">
                                <div class="metric-label">Speed</div>
                                <div class="metric-value">${tokensPerSecond.toFixed(1)} tokens/sec</div>
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-icon"><i class="fas fa-coins"></i></div>
                            <div class="metric-content">
                                <div class="metric-label">Total Tokens</div>
                                <div class="metric-value">${totalTokens.toLocaleString()}</div>
                            </div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-icon"><i class="fas fa-arrow-right"></i></div>
                            <div class="metric-content">
                                <div class="metric-label">Input → Output</div>
                                <div class="metric-value">${inputTokens.toLocaleString()} → ${outputTokens.toLocaleString()}</div>
                            </div>
                        </div>
                        ${metrics.model ? `
                        <div class="metric-card full-width">
                            <div class="metric-icon"><i class="fas fa-brain"></i></div>
                            <div class="metric-content">
                                <div class="metric-label">Model</div>
                                <div class="metric-value">${metrics.model}</div>
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }
    
    createEnhancedSourcesHTML(sources) {
        if (!sources || sources.length === 0) return '';
        
        const sourcesHTML = sources.map((source, index) => {
            const icon = this.sourceTemplates[source.type] || this.sourceTemplates.default;
            const confidence = source.score || source.confidence || 0;
            const category = source.category || source.main_category || 'Uncategorized';
            const subcategory = source.subcategory || source.sub_category || '';
            
            return `
                <div class="source-item enhanced-source" data-source-index="${index}">
                    <div class="source-header">
                        <div class="source-icon">${icon}</div>
                        <div class="source-title-section">
                            <div class="source-title">${source.title || 'Untitled'}</div>
                            <div class="source-metadata">
                                <span class="source-category">${category}${subcategory ? ` / ${subcategory}` : ''}</span>
                                <span class="source-confidence" title="Relevance Score">
                                    ${(confidence * 100).toFixed(1)}% match
                                </span>
                            </div>
                        </div>
                        <div class="source-actions">
                            <button class="source-action-btn" data-action="view" title="View Full Document">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="source-action-btn" data-action="copy" title="Copy Reference">
                                <i class="fas fa-copy"></i>
                            </button>
                        </div>
                    </div>
                    ${source.content ? `
                    <div class="source-preview">
                        <div class="source-content">${this.truncateText(source.content, 200)}</div>
                    </div>
                    ` : ''}
                </div>
            `;
        }).join('');
        
        return `
            <div class="message-sources enhanced-sources">
                <div class="sources-header">
                    <div class="sources-title-section">
                        <i class="fas fa-book-open"></i>
                        <span class="sources-title">Sources</span>
                        <span class="sources-count">${sources.length}</span>
                    </div>
                    <button class="sources-toggle" title="Toggle Sources">
                        <i class="fas fa-chevron-down"></i>
                    </button>
                </div>
                <div class="sources-content">
                    ${sourcesHTML}
                </div>
            </div>
        `;
    }
    
    createMessageHeaderActions(message) {
        const isUser = message.role === 'user';
        return `
            <div class="message-header-actions">
                ${!isUser ? `
                <button class="header-action-btn model-info-btn" title="Model Information">
                    <i class="fas fa-info-circle"></i>
                </button>
                ` : ''}
                <button class="header-action-btn timestamp-btn" title="Message Details">
                    <i class="fas fa-clock"></i>
                </button>
            </div>
        `;
    }
    
    createEnhancedMessageActions(message) {
        const isUser = message.role === 'user';
        return `
            <div class="message-actions enhanced-actions">
                <button class="message-action copy-btn" data-action="copy" title="Copy Message">
                    <i class="fas fa-copy"></i>
                    <span class="action-label">Copy</span>
                </button>
                ${!isUser ? `
                <button class="message-action regenerate-btn" data-action="regenerate" title="Regenerate Response">
                    <i class="fas fa-redo"></i>
                    <span class="action-label">Regenerate</span>
                </button>
                <button class="message-action improve-btn" data-action="improve" title="Improve Response">
                    <i class="fas fa-magic"></i>
                    <span class="action-label">Improve</span>
                </button>
                ` : ''}
                <button class="message-action share-btn" data-action="share" title="Share Message">
                    <i class="fas fa-share"></i>
                    <span class="action-label">Share</span>
                </button>
                <button class="message-action bookmark-btn" data-action="bookmark" title="Bookmark Message">
                    <i class="fas fa-bookmark"></i>
                    <span class="action-label">Bookmark</span>
                </button>
            </div>
        `;
    }
    
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength).trim() + '...';
    }
    
    async setupEventListeners() {
        // Set up event listeners for enhanced functionality
        this.eventService.setupStandardListeners(this, {
            delegated: [
                {
                    container: document.body,
                    selector: '.code-copy-btn',
                    event: 'click',
                    handler: this.handleCodeCopy.bind(this)
                },
                {
                    container: document.body,
                    selector: '.performance-toggle',
                    event: 'click',
                    handler: this.handlePerformanceToggle.bind(this)
                },
                {
                    container: document.body,
                    selector: '.sources-toggle',
                    event: 'click',
                    handler: this.handleSourcesToggle.bind(this)
                },
                {
                    container: document.body,
                    selector: '.kb-reference',
                    event: 'click',
                    handler: this.handleKBReference.bind(this)
                },
                {
                    container: document.body,
                    selector: '.source-action-btn',
                    event: 'click',
                    handler: this.handleSourceAction.bind(this)
                },
                {
                    container: document.body,
                    selector: '.message-action',
                    event: 'click',
                    handler: this.handleMessageAction.bind(this)
                }
            ]
        });
    }
    
    handleCodeCopy(event) {
        const button = event.target.closest('.code-copy-btn');
        const code = button.dataset.code;
        
        if (navigator.clipboard) {
            navigator.clipboard.writeText(code).then(() => {
                this.showCopyFeedback(button);
            }).catch(err => {
                this.logError('Failed to copy code:', err);
            });
        }
    }
    
    handlePerformanceToggle(event) {
        const toggle = event.target.closest('.performance-toggle');
        const details = toggle.parentElement.querySelector('.performance-details');
        const icon = toggle.querySelector('i');
        
        details.classList.toggle('hidden');
        icon.classList.toggle('fa-chart-bar');
        icon.classList.toggle('fa-chart-line');
    }
    
    handleSourcesToggle(event) {
        const toggle = event.target.closest('.sources-toggle');
        const content = toggle.closest('.message-sources').querySelector('.sources-content');
        const icon = toggle.querySelector('i');
        
        content.classList.toggle('hidden');
        icon.classList.toggle('fa-chevron-down');
        icon.classList.toggle('fa-chevron-up');
    }
    
    handleKBReference(event) {
        const reference = event.target.closest('.kb-reference');
        const kbItem = reference.dataset.kbItem;
        const synthesis = reference.dataset.synthesis;
        
        if (kbItem) {
            this.dispatchEvent('kbItemRequested', { item: kbItem });
        } else if (synthesis) {
            this.dispatchEvent('synthesisRequested', { synthesis: synthesis });
        }
    }
    
    handleSourceAction(event) {
        const button = event.target.closest('.source-action-btn');
        const action = button.dataset.action;
        const sourceItem = button.closest('.source-item');
        const sourceIndex = sourceItem.dataset.sourceIndex;
        
        this.dispatchEvent('sourceActionRequested', { 
            action: action, 
            sourceIndex: parseInt(sourceIndex) 
        });
    }
    
    handleMessageAction(event) {
        const button = event.target.closest('.message-action');
        const action = button.dataset.action;
        const message = button.closest('.message');
        const messageId = message.dataset.messageId;
        
        this.dispatchEvent('messageActionRequested', { 
            action: action, 
            messageId: messageId,
            messageElement: message
        });
    }
    
    showCopyFeedback(button) {
        const originalIcon = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i>';
        button.classList.add('success');
        
        setTimeout(() => {
            button.innerHTML = originalIcon;
            button.classList.remove('success');
        }, 2000);
    }
}

// Export for use in other modules
window.EnhancedMessageRenderer = EnhancedMessageRenderer;