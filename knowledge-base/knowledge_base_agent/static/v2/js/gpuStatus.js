/* V2 GPUSTATUS.JS - PURE API POLLING GPU STATUS MANAGER */

class GpuStatusManager {
    constructor(api) {
        this.api = api;
        this.container = document.getElementById('gpu-status-container');
        
        if (!this.container) {
            console.warn('GPU status container not found');
            return;
        }

        this.init();
    }

    init() {
        this.loadInitialGpuStats();
        this.setupEventListeners();
    }

    async loadInitialGpuStats() {
        try {
            console.log('🔧 Loading GPU statistics...');
            const response = await this.api.request('/gpu-stats');
            
            if (response && response.gpus) {
                this.updateGpuStats({ gpus: response.gpus });
            } else if (response && response.error) {
                this.showNoGpuMessage(response.error);
            } else {
                this.showNoGpuMessage('No GPU data available');
            }
        } catch (error) {
            console.error('Failed to load GPU stats:', error);
            this.showNoGpuMessage('Failed to load GPU statistics');
        }
    }

    setupEventListeners() {
        // Listen for real-time GPU updates via polling system
        document.addEventListener('gpu_stats_update', (event) => {
            this.updateGpuStats(event.detail);
        });
    }

    updateGpuStats(data) {
        if (!this.container) return;

        if (!data || !data.gpus) {
            console.warn('GPU container found but no GPU data received.');
            this.showNoGpuMessage('No GPU detected or nvidia-smi not available');
            return;
        }

        if (data.gpus.length === 0) {
            this.showNoGpuMessage('No GPUs detected');
            return;
        }

        // Clear previous stats
        this.container.innerHTML = '';

        // Create GPU cards using CSS classes
        data.gpus.forEach((gpu, index) => {
            const gpuCard = this.createGpuCard(gpu, index);
            this.container.appendChild(gpuCard);
        });

        // Initialize UI effects if available
        if (window.UIEffects) {
            new window.UIEffects();
        }
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
                </div>
            </div>
        `;
        
        return card;
    }

    showNoGpuMessage(message) {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="no-gpu-panel">
                <i class="fas fa-microchip"></i>
                <p>${message}</p>
            </div>
        `;
    }

    // === PUBLIC API ===
    
    refresh() {
        this.loadInitialGpuStats();
    }
}

// Make globally available for non-module usage
window.GpuStatusManager = GpuStatusManager; 