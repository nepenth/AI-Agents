/* V2 GPUSTATUS.JS - ENHANCED GPU STATUS MANAGER */

class GpuStatusManager {
    constructor(api) {
        this.api = api;
        this.container = document.getElementById('gpu-status-container');
        
        if (!this.container) {
            console.warn('GPU status container not found');
            return;
        }

        // State management
        this.gpuData = null;
        this.updateInterval = null;
        this.isLoading = false;
        this.socketConnected = false;

        this.init();
    }

    init() {
        this.loadInitialGpuStats();
        this.setupEventListeners();
        this.startPeriodicUpdates();
    }

    async loadInitialGpuStats() {
        if (this.isLoading) return;
        
        try {
            this.isLoading = true;
            console.log('🔧 Loading GPU statistics...');
            
            // Show loading state
            this.showLoadingState();
            
            const response = await this.api.request('/gpu-stats');
            console.log('🔧 GPU API response:', response);
            
            if (response && response.gpus && Array.isArray(response.gpus)) {
                this.gpuData = response;
                this.updateGpuStats(response);
            } else if (response && response.error) {
                console.warn('GPU API returned error:', response.error);
                this.showNoGpuMessage(response.error);
            } else {
                console.warn('GPU API returned unexpected format:', response);
                this.showNoGpuMessage('No GPU data available');
            }
        } catch (error) {
            console.error('Failed to load GPU stats:', error);
            this.showNoGpuMessage(`Failed to load GPU statistics: ${error.message}`);
        } finally {
            this.isLoading = false;
        }
    }

    startPeriodicUpdates() {
        // CRITICAL FIX: Only use periodic updates as fallback when SocketIO is not available
        // Primary updates should come from SocketIO events
        this.updateInterval = setInterval(() => {
            // Only update if SocketIO is not connected and container is visible
            if (!this.socketConnected && !this.isLoading && this.container && this.container.offsetParent !== null) {
                console.log('🔧 Using fallback polling for GPU stats (SocketIO not available)');
                this.loadInitialGpuStats();
            }
        }, 30000); // Increased to 30 seconds since this is just fallback
    }

    showLoadingState() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="gpu-loading-state">
                <div class="loading-spinner"></div>
                <span>Loading GPU statistics...</span>
            </div>
        `;
    }

    setupEventListeners() {
        // Use centralized EventListenerService
        EventListenerService.setupStandardListeners(this, {
            customEvents: [
                {
                    event: 'gpu_stats',
                    handler: (e) => {
                        console.log('🔧 GPU stats event received:', e.detail);
                        this.updateGpuStats(e.detail);
                    }
                },
                {
                    event: 'gpu_stats_update',
                    handler: (e) => {
                        console.log('🔧 GPU stats update event received:', e.detail);
                        this.updateGpuStats(e.detail);
                    }
                },
                {
                    event: 'socketio-ready',
                    handler: () => this.initializeSocketIOListeners()
                },
                {
                    event: 'socketio-failed',
                    handler: () => {
                        console.warn('SocketIO not available for GPU stats - using polling only');
                    }
                }
            ]
        });
        
        // Set up SocketIO listeners
        this.setupSocketIOListeners();
    }

    setupSocketIOListeners() {
        // Listen for SocketIO ready event from the async loader
        document.addEventListener('socketio-ready', () => {
            this.initializeSocketIOListeners();
        });
        
        document.addEventListener('socketio-failed', () => {
            console.warn('SocketIO not available for GPU stats - using polling only');
        });
        
        // Check if SocketIO is already available (in case we missed the event)
        if (window.socket) {
            this.initializeSocketIOListeners();
        }
    }
    
    initializeSocketIOListeners() {
        if (!window.socket) {
            console.warn('SocketIO not available for GPU stats');
            return;
        }
        
        console.log('🔧 Setting up SocketIO listeners for GPU stats');
        
        // Track connection status
        window.socket.on('connect', () => {
            this.socketConnected = true;
            console.log('🔗 SocketIO connected for GPU stats');
        });
        
        window.socket.on('disconnect', () => {
            this.socketConnected = false;
            console.log('🔗 SocketIO disconnected for GPU stats');
        });
        
        // Set initial connection status
        this.socketConnected = window.socket.connected;
        
        // Listen for GPU stats updates from SocketIO
        window.socket.on('gpu_stats', (data) => {
            console.log('🔧 GPU stats received via SocketIO:', data);
            this.updateGpuStats(data);
        });
        
        // Also listen for system health updates that might include GPU data
        window.socket.on('system_health_update', (data) => {
            if (data.gpu_stats) {
                console.log('🔧 GPU stats received via system health update:', data.gpu_stats);
                this.updateGpuStats(data.gpu_stats);
            }
        });
        
        console.log('✅ SocketIO listeners set up for GPU stats');
    }

    updateGpuStats(data) {
        if (!this.container) return;

        console.log('🔧 Updating GPU stats with data:', data);

        if (!data) {
            console.warn('GPU container found but no data received.');
            this.showNoGpuMessage('No GPU data received from server');
            return;
        }

        if (data.error) {
            console.warn('GPU API returned error:', data.error);
            this.showNoGpuMessage(data.error);
            return;
        }

        // CRITICAL FIX: Handle different GPU data formats
        let gpus = [];
        if (Array.isArray(data)) {
            // Direct array format
            gpus = data;
        } else if (data.gpus && Array.isArray(data.gpus)) {
            // Object with gpus property
            gpus = data.gpus;
        } else {
            console.warn('GPU data format invalid:', data);
            this.showNoGpuMessage('Invalid GPU data format received');
            return;
        }

        if (gpus.length === 0) {
            this.showNoGpuMessage('No NVIDIA GPUs detected on this system');
            return;
        }

        // Update data reference for comparison
        const normalizedData = { gpus };

        // CRITICAL FIX: Smart update logic to prevent flashing
        const existingCards = this.container.querySelectorAll('.gpu-card');
        const hasExistingCards = existingCards.length > 0;
        const needsRebuild = existingCards.length !== gpus.length;
        
        // Store current data to compare with new data
        const hasDataChanged = !this.gpuData || JSON.stringify(this.gpuData.gpus || this.gpuData) !== JSON.stringify(gpus);
        
        // Only rebuild if necessary (count changed or first time)
        if (needsRebuild || !hasExistingCards) {
            console.log('🔧 Rebuilding GPU cards (count changed or first load)');
            this.container.innerHTML = '';
            gpus.forEach((gpu, index) => {
                const gpuCard = this.createGpuCard(gpu, index);
                this.container.appendChild(gpuCard);
            });
        } else if (hasDataChanged) {
            // Only update if data actually changed
            console.log('🔧 Updating existing GPU cards (data changed)');
            gpus.forEach((gpu, index) => {
                this.updateExistingGpuCard(existingCards[index], gpu, index);
            });
        } else {
            console.log('🔧 Skipping GPU update (no data changes)');
            return; // No changes, skip update
        }

        // Store current data for next comparison
        this.gpuData = normalizedData;

        // Initialize UI effects only if cards were rebuilt
        if ((needsRebuild || !hasExistingCards) && window.UIEffects) {
            new window.UIEffects();
        }
    }

    updateExistingGpuCard(cardElement, gpu, index) {
        if (!cardElement) return;

        // Calculate values
        const loadPercentage = parseFloat(gpu.utilization_gpu || 0);
        const memoryUsedMB = parseFloat(gpu.memory_used || 0);
        const memoryTotalMB = parseFloat(gpu.memory_total || 1);
        const memoryUsedGB = memoryUsedMB / 1024;
        const memoryPercentage = (memoryUsedMB / memoryTotalMB) * 100;
        const tempCelsius = parseFloat(gpu.temperature_gpu || 0);
        const tempFahrenheit = (tempCelsius * 9/5) + 32;

        // Update values without rebuilding the entire card
        const stats = cardElement.querySelectorAll('.gpu-stat');
        
        // Update GPU Load
        if (stats[0]) {
            const valueEl = stats[0].querySelector('.gpu-stat-value');
            const progressBar = stats[0].querySelector('.gpu-progress-bar');
            if (valueEl) valueEl.innerHTML = `${loadPercentage.toFixed(1)}<span class="gpu-stat-unit">%</span>`;
            if (progressBar) {
                progressBar.style.setProperty('--progress-width', `${loadPercentage}%`);
                progressBar.className = `gpu-progress-bar ${this.getLoadClass(loadPercentage)}`;
            }
        }

        // Update Memory
        if (stats[1]) {
            const valueEl = stats[1].querySelector('.gpu-stat-value');
            const progressBar = stats[1].querySelector('.gpu-progress-bar');
            if (valueEl) valueEl.innerHTML = `${memoryUsedGB.toFixed(1)}<span class="gpu-stat-unit">GB</span>`;
            if (progressBar) {
                progressBar.style.setProperty('--progress-width', `${memoryPercentage}%`);
                progressBar.className = `gpu-progress-bar ${this.getMemoryClass(memoryPercentage)}`;
            }
        }

        // Update Temperature
        if (stats[2]) {
            const valueEl = stats[2].querySelector('.gpu-stat-value');
            const progressBar = stats[2].querySelector('.gpu-progress-bar');
            if (valueEl) {
                valueEl.innerHTML = `${tempFahrenheit.toFixed(1)}<span class="gpu-stat-unit">°F</span>`;
                valueEl.className = `gpu-stat-value ${this.getTempClass(tempFahrenheit)}`;
            }
            if (progressBar) {
                progressBar.style.setProperty('--progress-width', `${Math.min(100, tempFahrenheit / 2)}%`);
                progressBar.className = `gpu-progress-bar ${this.getTempClass(tempFahrenheit)}`;
            }
        }
    }

    getLoadClass(load) {
        if (load > 90) return 'load-high';
        if (load > 70) return 'load-medium';
        return 'load-low';
    }

    getMemoryClass(memory) {
        if (memory > 90) return 'memory-high';
        if (memory > 70) return 'memory-medium';
        return 'memory-low';
    }

    getTempClass(tempF) {
        if (tempF >= 176) return 'temp-hot';    // 80°C = 176°F
        if (tempF >= 149) return 'temp-warm';   // 65°C = 149°F
        return 'temp-cool';
    }

    createGpuCard(gpu, index) {
        const card = document.createElement('div');
        card.className = 'gpu-card';
        
        // Handle raw nvidia-smi data format
        const gpuName = gpu.name || `GPU ${index}`;
        const loadPercentage = parseFloat(gpu.utilization_gpu || 0);
        const memoryUsedMB = parseFloat(gpu.memory_used || 0);
        const memoryTotalMB = parseFloat(gpu.memory_total || 1);
        const memoryUsedGB = memoryUsedMB / 1024;
        const memoryTotalGB = memoryTotalMB / 1024;
        const memoryPercentage = (memoryUsedMB / memoryTotalMB) * 100;
        const tempCelsius = parseFloat(gpu.temperature_gpu || 0);
        const tempFahrenheit = (tempCelsius * 9/5) + 32; // Convert to Fahrenheit
        
        // Determine CSS classes for progress bars and temperature
        const getLoadClass = (load) => {
            if (load > 90) return 'load-high';
            if (load > 70) return 'load-medium';
            return 'load-low';
        };
        
        const getMemoryClass = (memory) => {
            if (memory > 90) return 'memory-high';
            if (memory > 70) return 'memory-medium';
            return 'memory-low';
        };
        
        const getTempClass = (tempF) => {
            if (tempF >= 176) return 'temp-hot';    // 80°C = 176°F
            if (tempF >= 149) return 'temp-warm';   // 65°C = 149°F
            return 'temp-cool';
        };
        
        const loadClass = getLoadClass(loadPercentage);
        const memoryClass = getMemoryClass(memoryPercentage);
        const tempClass = getTempClass(tempFahrenheit);
        
        card.innerHTML = `
            <div class="gpu-card-header">
                <span class="gpu-name">${gpuName}</span>
                <span class="gpu-id">GPU ${index}</span>
            </div>
            
            <div class="gpu-stats">
                <div class="gpu-stat">
                    <div class="gpu-stat-label">GPU Load</div>
                    <div class="gpu-stat-value">${loadPercentage.toFixed(1)}<span class="gpu-stat-unit">%</span></div>
                    <div class="gpu-progress">
                        <div class="gpu-progress-bar ${loadClass}" style="--progress-width: ${loadPercentage}%;"></div>
                    </div>
                </div>
                
                <div class="gpu-stat">
                    <div class="gpu-stat-label">Memory</div>
                    <div class="gpu-stat-value">${memoryUsedGB.toFixed(1)}<span class="gpu-stat-unit">GB</span></div>
                    <div class="gpu-progress">
                        <div class="gpu-progress-bar ${memoryClass}" style="--progress-width: ${memoryPercentage}%;"></div>
                    </div>
                </div>
                
                <div class="gpu-stat">
                    <div class="gpu-stat-label">Temperature</div>
                    <div class="gpu-stat-value ${tempClass}">${tempFahrenheit.toFixed(1)}<span class="gpu-stat-unit">°F</span></div>
                    <div class="gpu-progress">
                        <div class="gpu-progress-bar ${tempClass}" style="--progress-width: ${Math.min(100, tempFahrenheit / 2)}%;"></div>
                    </div>
                </div>
            </div>
        `;
        
        return card;
    }

    showNoGpuMessage(message) {
        if (!this.container) return;
        
        // Determine the appropriate icon and enhanced message based on the error
        let icon = 'fas fa-microchip';
        let enhancedMessage = message;
        
        if (message.includes('nvidia-smi')) {
            icon = 'fas fa-exclamation-triangle';
            enhancedMessage = 'NVIDIA drivers not installed or nvidia-smi not available';
        } else if (message.includes('No GPU') || message.includes('No NVIDIA')) {
            icon = 'fas fa-info-circle';
            enhancedMessage = 'No NVIDIA GPUs detected on this system';
        } else if (message.includes('Failed to load')) {
            icon = 'fas fa-exclamation-circle';
            enhancedMessage = 'Failed to load GPU statistics from server';
        }
        
        this.container.innerHTML = `
            <div class="gpu-no-gpu-message">
                <i class="${icon}"></i>
                <p>${enhancedMessage}</p>
                <small style="margin-top: 8px; opacity: 0.7;">
                    ${message.includes('nvidia-smi') ? 
                        'Install NVIDIA drivers and nvidia-smi to view GPU statistics' : 
                        'GPU monitoring requires NVIDIA graphics cards'
                    }
                </small>
            </div>
        `;
    }

    // === PUBLIC API ===
    
    refresh() {
        this.loadInitialGpuStats();
    }
    
    cleanup() {
        // Clear the update interval
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        // Use CleanupService if available
        if (window.CleanupService) {
            CleanupService.cleanup(this);
        }
        
        console.log('🧹 GpuStatusManager cleanup complete');
    }
}

// Make globally available for non-module usage
window.GpuStatusManager = GpuStatusManager; 