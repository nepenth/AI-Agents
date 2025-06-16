//
//
//
// knowledge_base_agent/static/js/syntheses.js
function initializeSynthesesPage() {
    console.log("Initializing syntheses page...");

    const synthesisList = document.getElementById('synthesis-list');
    const regenerateAllBtn = document.getElementById('regenerate-all-syntheses');

    async function loadSyntheses() {
        if (!synthesisList) return;
        try {
            const response = await fetch('/api/synthesis');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const syntheses = await response.json();

            synthesisList.innerHTML = ''; // Clear loading message

            if (syntheses.length === 0) {
                synthesisList.innerHTML = '<p>No synthesis documents found.</p>';
                return;
            }

            const listGroup = document.createElement('div');
            listGroup.className = 'list-group';

            syntheses.forEach(synth => {
                const item = document.createElement('a');
                item.href = `#`; // Link to the detail view
                item.className = 'list-group-item list-group-item-action';
                item.dataset.page = `synthesis/${synth.id}`; // For SPA navigation
                item.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">${synth.title}</h5>
                        <small>Last updated: ${new Date(synth.last_updated).toLocaleString()}</small>
                    </div>
                    <p class="mb-1">${synth.summary || 'No summary available.'}</p>
                    <small>Topic: ${synth.topic}</small>
                `;
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    // Use the navigation system to load the page
                    if (window.navigationManager) {
                        window.navigationManager.loadPage(`synthesis/${synth.id}`);
                    }
                });
                listGroup.appendChild(item);
            });
            synthesisList.appendChild(listGroup);

        } catch (error) {
            console.error("Failed to load syntheses:", error);
            if (synthesisList) {
                synthesisList.innerHTML = '<div class="alert alert-danger">Error loading synthesis documents. Please try again.</div>';
            }
        }
    }

    if (regenerateAllBtn) {
        regenerateAllBtn.addEventListener('click', async () => {
            if (!confirm('Are you sure you want to regenerate all synthesis documents? This can be slow and costly.')) {
                return;
            }
            try {
                const response = await fetch('/api/synthesis/regenerate-all', { method: 'POST' });
                if (!response.ok) throw new Error('Failed to start regeneration.');
                const result = await response.json();
                alert(result.message || 'Regeneration process started.');
                loadSyntheses(); // Refresh list
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        });
    }

    // Initial load
    loadSyntheses();
}

window.initializeSynthesesPage = initializeSynthesesPage; 