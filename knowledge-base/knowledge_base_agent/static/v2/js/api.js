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
}

window.API = API; 