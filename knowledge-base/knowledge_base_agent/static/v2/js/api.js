/* Shared fetch wrapper – lightweight alternative to UI.js APIClient */

class API {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
    }

    async request(endpoint, { method = 'GET', headers = {}, body = null } = {}) {
        const cfg = { method, headers: { 'Content-Type': 'application/json', ...headers } };
        if (body) cfg.body = typeof body === 'string' ? body : JSON.stringify(body);
        try {
            const res = await fetch(`${this.baseURL}${endpoint}`, cfg);
            if (!res.ok) {
                const text = await res.text();
                throw new Error(`HTTP ${res.status} – ${text || res.statusText}`);
            }
            const ct = res.headers.get('content-type') || '';
            return ct.includes('application/json') ? res.json() : res.text();
        } catch (err) {
            console.error('API request error', err);
            throw err;
        }
    }

    // Agent Status Methods
    async getAgentStatus() {
        return this.request('/agent/status');
    }

    async resetAgentState() {
        return this.request('/agent/reset-state', { method: 'POST' });
    }

    // Agent Control Methods
    async startAgent(preferences = {}) {
        return this.request('/v2/agent/start', { 
            method: 'POST', 
            body: { preferences } 
        });
    }

    async stopAgent() {
        return this.request('/agent/stop', { method: 'POST' });
    }

    // Preferences Methods
    async getPreferences() {
        return this.request('/preferences');
    }

    async savePreferences(preferences) {
        return this.request('/preferences', { 
            method: 'POST', 
            body: preferences 
        });
    }

    // Alias for backward compatibility
    async updatePreferences(preferences) {
        return this.savePreferences(preferences);
    }
}

window.API = API; 