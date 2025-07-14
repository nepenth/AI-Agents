/* V2 SYNTHESIS.JS - SIMPLIFIED SYNTHESIS MANAGER */

class SynthesisManager {
    constructor(api) {
        this.api = api;
        this.syntheses = [];
        this.filteredSyntheses = [];
        this.currentSynthesis = null;
        this.currentView = 'list'; // 'list' or 'detail'
        
        // DOM elements will be initialized after content loads
        this.elements = {};
    }

    async initialize() {
        console.log('💡 SynthesisManager.initialize() called');
        
        try {
            // Load synthesis page content
            await this.loadPageContent();
            
            // Initialize DOM references
            this.initializeDOMReferences();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Load synthesis data
            await this.loadSynthesisData();
            
            console.log('✅ SynthesisManager initialized successfully');
        } catch (error) {
            console.error('❌ SynthesisManager initialization failed:', error);
            this.showError('Failed to initialize synthesis interface');
        }
    }

    async loadPageContent() {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            throw new Error('Main content container not found');
        }

        const response = await fetch('/v2/page/synthesis');
        if (!response.ok) {
            throw new Error(`Failed to load synthesis content: ${response.status}`);
        }

        const html = await response.text();
        mainContent.innerHTML = html;
        console.log('💡 Synthesis content loaded');
    }

    initializeDOMReferences() {
        this.elements = {
            // Stats in sidebar
            totalSyntheses: document.getElementById('synthesis-total-docs'),
            categoriesCovered: document.getElementById('synthesis-categories'),
            itemsSynthesized: document.getElementById('synthesis-items-analyzed'),
            lastUpdated: document.getElementById('synthesis-last-generated'),
            
            // Overview metrics (in main content)
            overviewTotal: document.getElementById('overview-synthesis-total'),
            overviewCategories: document.getElementById('overview-synthesis-categories'),
            overviewItems: document.getElementById('overview-items-synthesized'),
            overviewRecent: document.getElementById('overview-recent-count'),
            
            // Controls
            searchInput: document.getElementById('v2-synthesis-search'),
            refreshBtn: document.getElementById('synthesis-refresh-data'),
            exportAllBtn: document.getElementById('synthesis-export-all'),
            generateNewBtn: document.getElementById('synthesis-generate-new'),
            
            // Tree container
            treeContainer: document.getElementById('synthesis-tree-container'),
            
            // Content views
            overviewView: document.getElementById('synthesis-overview-view'),
            categoryView: document.getElementById('synthesis-category-view'),
            documentView: document.getElementById('synthesis-document-view'),
            
            // Category view elements
            categoryTitle: document.getElementById('synthesis-category-title'),
            categoryDescription: document.getElementById('synthesis-category-description'),
            categoryDocs: document.getElementById('synthesis-category-docs'),
            categoryUpdated: document.getElementById('synthesis-category-updated'),
            categoryContent: document.getElementById('synthesis-category-content'),
            
            // Document view elements
            documentContent: document.getElementById('synthesis-document-content'),
            backToCategoryBtn: document.getElementById('synthesis-back-to-category'),
            regenerateBtn: document.getElementById('synthesis-regenerate-doc'),
            exportSingleBtn: document.getElementById('synthesis-export-doc'),
            
            // Quick action buttons
            browseRecentBtn: document.getElementById('browse-recent-syntheses'),
            generateBtn: document.getElementById('generate-new-synthesis'),
            viewAllCategoriesBtn: document.getElementById('view-all-categories')
        };

        console.log('💡 DOM references initialized:', Object.keys(this.elements).length, 'elements');
        
        // Log missing elements for debugging
        const missingElements = Object.entries(this.elements)
            .filter(([key, element]) => !element)
            .map(([key]) => key);
        
        if (missingElements.length > 0) {
            console.warn('⚠️ Missing DOM elements:', missingElements);
        }
    }

    setupEventListeners() {
        // Search functionality
        if (this.elements.searchInput) {
            this.elements.searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
        }

        // Refresh button
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.addEventListener('click', () => {
                this.refresh();
            });
        }

        // Export all button
        if (this.elements.exportAllBtn) {
            this.elements.exportAllBtn.addEventListener('click', () => {
                this.exportAll();
            });
        }

        // Generate new synthesis button
        if (this.elements.generateNewBtn) {
            this.elements.generateNewBtn.addEventListener('click', () => {
                this.generateNewSynthesis();
            });
        }

        // Back to category button
        if (this.elements.backToCategoryBtn) {
            this.elements.backToCategoryBtn.addEventListener('click', () => {
                this.showOverview();
            });
        }

        // Single document actions
        if (this.elements.regenerateBtn) {
            this.elements.regenerateBtn.addEventListener('click', () => {
                this.regenerateCurrent();
            });
        }

        if (this.elements.exportSingleBtn) {
            this.elements.exportSingleBtn.addEventListener('click', () => {
                this.exportCurrent();
            });
        }

        // Quick action buttons
        if (this.elements.browseRecentBtn) {
            this.elements.browseRecentBtn.addEventListener('click', () => {
                this.browseRecent();
            });
        }

        if (this.elements.generateBtn) {
            this.elements.generateBtn.addEventListener('click', () => {
                this.generateNewSynthesis();
            });
        }

        if (this.elements.viewAllCategoriesBtn) {
            this.elements.viewAllCategoriesBtn.addEventListener('click', () => {
                this.expandAllCategories();
            });
        }

        console.log('🎧 Event listeners set up');
    }

    async loadSynthesisData() {
        try {
            console.log('📊 Loading synthesis data...');
            const response = await this.api.request('/syntheses');
            this.syntheses = response || [];
            this.filteredSyntheses = [...this.syntheses];
            
            this.updateStatistics();
            this.renderSynthesisList();
            
            console.log(`✅ Loaded ${this.syntheses.length} synthesis documents`);
        } catch (error) {
            console.error('❌ Error loading synthesis data:', error);
            this.showError('Failed to load synthesis documents');
        }
    }

    updateStatistics() {
        const totalSyntheses = this.syntheses.length;
        const categories = new Set(this.syntheses.map(s => s.main_category)).size;
        const totalItems = this.syntheses.reduce((sum, s) => sum + (s.item_count || 0), 0);
        const lastUpdate = this.syntheses.length > 0 ? 
            Math.max(...this.syntheses.map(s => new Date(s.last_updated || s.created_at).getTime())) : null;

        // Update sidebar stats
        if (this.elements.totalSyntheses) {
            this.elements.totalSyntheses.textContent = totalSyntheses;
        }
        if (this.elements.categoriesCovered) {
            this.elements.categoriesCovered.textContent = categories;
        }
        if (this.elements.itemsSynthesized) {
            this.elements.itemsSynthesized.textContent = totalItems;
        }
        if (this.elements.lastUpdated) {
            this.elements.lastUpdated.textContent = lastUpdate ? 
                this.formatDate(new Date(lastUpdate)) : '--';
        }

        // Update overview metrics
        if (this.elements.overviewTotal) {
            this.elements.overviewTotal.textContent = totalSyntheses;
        }
        if (this.elements.overviewCategories) {
            this.elements.overviewCategories.textContent = categories;
        }
        if (this.elements.overviewItems) {
            this.elements.overviewItems.textContent = totalItems;
        }
        if (this.elements.overviewRecent) {
            // Count syntheses updated in last 7 days
            const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
            const recentCount = this.syntheses.filter(s => 
                new Date(s.last_updated || s.created_at) > weekAgo
            ).length;
            this.elements.overviewRecent.textContent = recentCount;
        }
    }

    renderSynthesisList() {
        if (!this.elements.treeContainer) {
            console.warn('Tree container not found');
            return;
        }

        if (this.filteredSyntheses.length === 0) {
            this.elements.treeContainer.innerHTML = `
                <div class="placeholder-state">
                    <div class="placeholder-icon">
                        <i class="fas fa-lightbulb"></i>
                    </div>
                    <h3 class="placeholder-title">No Synthesis Documents</h3>
                    <p class="placeholder-description">
                        No synthesis documents found. Run the agent with synthesis generation enabled to create documents.
                    </p>
                    <div class="placeholder-actions">
                        <button class="glass-button glass-button--primary" onclick="window.router.navigate('dashboard')">
                            <i class="fas fa-robot"></i>
                            <span>Go to Agent Dashboard</span>
                        </button>
                        <button class="glass-button glass-button--secondary" onclick="this.refresh()">
                            <i class="fas fa-sync-alt"></i>
                            <span>Refresh</span>
                        </button>
                    </div>
                </div>
            `;
            return;
        }

        // Group syntheses by category
        const categorizedSyntheses = {};
        this.filteredSyntheses.forEach(synthesis => {
            const category = synthesis.main_category || 'Uncategorized';
            if (!categorizedSyntheses[category]) {
                categorizedSyntheses[category] = [];
            }
            categorizedSyntheses[category].push(synthesis);
        });

        // Sort categories and syntheses
        const sortedCategories = Object.keys(categorizedSyntheses).sort();
        
        let treeHTML = '<div class="synthesis-tree">';
        
        sortedCategories.forEach(category => {
            const syntheses = categorizedSyntheses[category].sort((a, b) => 
                new Date(b.last_updated || b.created_at) - new Date(a.last_updated || a.created_at)
            );
            
            const categoryId = `synthesis-category-${category.replace(/[^a-zA-Z0-9]/g, '-')}`;
            
            treeHTML += `
                <div class="tree-category" data-category="${category}">
                    <div class="category-header" data-category="${category}">
                        <i class="fas fa-chevron-right category-toggle"></i>
                        <i class="fas fa-folder category-icon"></i>
                        <span class="category-name">${this.escapeHtml(category)}</span>
                        <span class="category-count">(${syntheses.length})</span>
                    </div>
                    <div class="subcategory-list" style="display: none;">
            `;
            
            syntheses.forEach(synthesis => {
                const lastUpdated = new Date(synthesis.last_updated || synthesis.created_at);
                const relativeTime = this.getRelativeTime(lastUpdated);
                
                treeHTML += `
                    <div class="tree-item synthesis-item" data-synthesis-id="${synthesis.id}">
                        <i class="fas fa-file-text item-icon"></i>
                        <div class="item-content">
                            <div class="item-title">${this.escapeHtml(synthesis.synthesis_title || 'Untitled')}</div>
                            <div class="item-meta">
                                <span class="item-count">${synthesis.item_count} items</span>
                                <span class="item-updated">${relativeTime}</span>
                            </div>
                        </div>
                        <div class="item-actions">
                            <button class="item-action-btn" onclick="event.stopPropagation(); this.viewSynthesis(${synthesis.id})" title="View">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="item-action-btn" onclick="event.stopPropagation(); this.exportSynthesis(${synthesis.id})" title="Export">
                                <i class="fas fa-download"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
            
            treeHTML += `
                    </div>
                </div>
            `;
        });
        
        treeHTML += '</div>';
        
        this.elements.treeContainer.innerHTML = treeHTML;
        
        // Add click handlers for categories
        this.elements.treeContainer.querySelectorAll('.category-header').forEach(header => {
            header.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleCategory(header);
            });
        });
        
        // Add click handlers for synthesis items
        this.elements.treeContainer.querySelectorAll('.synthesis-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.item-action-btn')) {
                    const synthesisId = parseInt(item.dataset.synthesisId);
                    this.viewSynthesis(synthesisId);
                }
            });
        });
        
        console.log(`📊 Rendered tree with ${sortedCategories.length} categories and ${this.filteredSyntheses.length} synthesis documents`);
    }

    toggleCategory(header) {
        const category = header.closest('.tree-category');
        const subcategoryList = category.querySelector('.subcategory-list');
        const toggle = header.querySelector('.category-toggle');
        
        if (subcategoryList.style.display === 'none') {
            subcategoryList.style.display = 'block';
            toggle.style.transform = 'rotate(90deg)';
            header.classList.add('expanded');
        } else {
            subcategoryList.style.display = 'none';
            toggle.style.transform = 'rotate(0deg)';
            header.classList.remove('expanded');
        }
    }

    async viewSynthesis(synthesisId) {
        try {
            console.log(`📖 Loading synthesis detail for ID: ${synthesisId}`);
            
            // Find synthesis in our data
            const synthesis = this.syntheses.find(s => s.id == synthesisId);
            if (!synthesis) {
                throw new Error('Synthesis not found');
            }

            // Load full synthesis data
            const response = await this.api.request(`/synthesis/${synthesisId}`);
            this.currentSynthesis = response;
            
            this.showSynthesisDetail(synthesis);
            
        } catch (error) {
            console.error('❌ Error loading synthesis detail:', error);
            this.showError('Failed to load synthesis document');
        }
    }

    showSynthesisDetail(synthesis) {
        // Hide overview and category views
        if (this.elements.overviewView) this.elements.overviewView.classList.remove('active');
        if (this.elements.categoryView) this.elements.categoryView.classList.remove('active');
        
        // Show document view
        if (this.elements.documentView) {
            this.elements.documentView.classList.add('active');
            
            // Update document content
            if (this.elements.documentContent && this.currentSynthesis) {
                this.elements.documentContent.innerHTML = `
                    <div class="document-header-info">
                        <h1 class="document-title">${this.escapeHtml(this.currentSynthesis.synthesis_title || 'Untitled')}</h1>
                        <div class="document-meta">
                            <span class="meta-item">
                                <i class="fas fa-folder"></i>
                                ${this.escapeHtml(this.currentSynthesis.main_category || 'Uncategorized')}
                            </span>
                            <span class="meta-item">
                                <i class="fas fa-file-text"></i>
                                ${this.currentSynthesis.item_count || 0} items analyzed
                            </span>
                            <span class="meta-item">
                                <i class="fas fa-clock"></i>
                                ${this.formatDate(new Date(this.currentSynthesis.last_updated || this.currentSynthesis.created_at))}
                            </span>
                        </div>
                    </div>
                    <div class="document-content-body">
                        ${this.currentSynthesis.synthesis_content_html || this.formatSynthesisContent(this.currentSynthesis.synthesis_content)}
                    </div>
                `;
            }
        }
    }

    showOverview() {
        // Hide other views
        if (this.elements.categoryView) this.elements.categoryView.classList.remove('active');
        if (this.elements.documentView) this.elements.documentView.classList.remove('active');
        
        // Show overview
        if (this.elements.overviewView) this.elements.overviewView.classList.add('active');
    }

    getRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
        if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
        return `${Math.floor(diffDays / 365)} years ago`;
    }

    exportSynthesis(synthesisId) {
        // Find synthesis
        const synthesis = this.syntheses.find(s => s.id == synthesisId);
        if (!synthesis) {
            console.error('Synthesis not found for export');
            return;
        }
        
        // Create export content
        const content = `# ${synthesis.synthesis_title || 'Untitled'}\n\n` +
                       `**Category:** ${synthesis.main_category || 'Uncategorized'}\n` +
                       `**Items Analyzed:** ${synthesis.item_count || 0}\n` +
                       `**Last Updated:** ${this.formatDate(new Date(synthesis.last_updated || synthesis.created_at))}\n\n` +
                       `---\n\n` +
                       `${synthesis.synthesis_content || 'No content available'}`;
        
        // Download file
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `synthesis-${synthesis.id}-${(synthesis.synthesis_title || 'untitled').replace(/[^a-zA-Z0-9]/g, '-')}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        console.log(`📥 Exported synthesis: ${synthesis.synthesis_title}`);
    }

    generateNewSynthesis() {
        // Navigate to agent dashboard to generate new synthesis
        window.router.navigate('dashboard');
        // Could show a notification about how to generate new syntheses
        console.log('🔄 Navigating to dashboard to generate new synthesis');
    }

    browseRecent() {
        // Filter to show only recent syntheses (last 7 days)
        const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
        this.filteredSyntheses = this.syntheses.filter(s => 
            new Date(s.last_updated || s.created_at) > weekAgo
        );
        this.renderSynthesisList();
        console.log(`📅 Showing ${this.filteredSyntheses.length} recent syntheses`);
    }

    expandAllCategories() {
        // Expand all categories in the tree
        if (this.elements.treeContainer) {
            const categories = this.elements.treeContainer.querySelectorAll('.tree-category');
            categories.forEach(category => {
                const header = category.querySelector('.category-header');
                const subcategoryList = category.querySelector('.subcategory-list');
                const toggle = header.querySelector('.category-toggle');
                
                if (subcategoryList && subcategoryList.style.display === 'none') {
                    subcategoryList.style.display = 'block';
                    toggle.style.transform = 'rotate(90deg)';
                    header.classList.add('expanded');
                }
            });
        }
        console.log('📂 Expanded all categories');
    }

    handleSearch(query) {
        if (!query.trim()) {
            this.filteredSyntheses = [...this.syntheses];
        } else {
            const searchLower = query.toLowerCase();
            this.filteredSyntheses = this.syntheses.filter(synthesis => 
                (synthesis.synthesis_title || '').toLowerCase().includes(searchLower) ||
                (synthesis.main_category || '').toLowerCase().includes(searchLower) ||
                (synthesis.synthesis_content || '').toLowerCase().includes(searchLower)
            );
        }
        this.renderSynthesisList();
        console.log(`🔍 Search results: ${this.filteredSyntheses.length} syntheses`);
    }

    async refresh() {
        console.log('🔄 Refreshing synthesis data...');
        await this.loadSynthesisData();
    }

    exportAll() {
        if (this.syntheses.length === 0) {
            console.warn('No syntheses to export');
            return;
        }

        // Create combined export content
        let content = '# Synthesis Documents Export\n\n';
        content += `Generated on: ${new Date().toISOString()}\n`;
        content += `Total documents: ${this.syntheses.length}\n\n`;
        content += '---\n\n';

        this.syntheses.forEach((synthesis, index) => {
            content += `## ${index + 1}. ${synthesis.synthesis_title || 'Untitled'}\n\n`;
            content += `**Category:** ${synthesis.main_category || 'Uncategorized'}\n`;
            content += `**Items Analyzed:** ${synthesis.item_count || 0}\n`;
            content += `**Last Updated:** ${this.formatDate(new Date(synthesis.last_updated || synthesis.created_at))}\n\n`;
            content += `${synthesis.synthesis_content || 'No content available'}\n\n`;
            content += '---\n\n';
        });

        // Download file
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `all-syntheses-${new Date().toISOString().split('T')[0]}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        console.log(`📥 Exported ${this.syntheses.length} synthesis documents`);
    }

    exportCurrent() {
        if (this.currentSynthesis) {
            this.exportSynthesis(this.currentSynthesis.id);
        }
    }

    regenerateCurrent() {
        if (this.currentSynthesis) {
            console.log(`🔄 Regenerating synthesis: ${this.currentSynthesis.synthesis_title}`);
            // This would need to be implemented with a backend API call
            alert('Synthesis regeneration feature would be implemented here');
        }
    }

    showError(message) {
        console.error(message);
        if (this.elements.treeContainer) {
            this.elements.treeContainer.innerHTML = `
                <div class="placeholder-state">
                    <div class="placeholder-icon">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <h3 class="placeholder-title">Error Loading Synthesis Documents</h3>
                    <p class="placeholder-description">${this.escapeHtml(message)}</p>
                    <div class="placeholder-actions">
                        <button class="glass-button glass-button--primary" onclick="location.reload()">
                            <i class="fas fa-refresh"></i> 
                            <span>Reload Page</span>
                        </button>
                        <button class="glass-button glass-button--secondary" onclick="window.router.navigate('dashboard')">
                            <i class="fas fa-home"></i> 
                            <span>Go to Dashboard</span>
                        </button>
                    </div>
                </div>
            `;
        }
    }

    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    formatDate(date) {
        if (!date || !(date instanceof Date)) return '--';
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    formatSynthesisContent(content) {
        if (!content) return '<p>No content available</p>';
        
        // Simple markdown-like formatting
        return content
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }

    cleanup() {
        // Clean up any event listeners or resources
        console.log('🧹 Cleaning up SynthesisManager');
    }
}

// Make globally available for router usage
window.SynthesisManager = SynthesisManager; 