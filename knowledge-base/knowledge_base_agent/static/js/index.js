document.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        const header = document.querySelector('.header');
        if (header) {
            header.classList.add('dark-mode');
        }
    }
    $('[data-bs-toggle="tooltip"]').tooltip();
    connectToSocketIO();
    loadCheckboxStates();
    updateAgentStatus();
});

function connectToSocketIO() {
    var socket = io.connect('http://' + document.domain + ':' + location.port);
    socket.on('connect', function() {
        console.log('Connected to server');
        socket.emit('log', {message: 'Connected to server', level: 'INFO'});
    });
    socket.on('log', function(data) {
        appendLog(data.message, data.level);
    });
    socket.on('progress', function(data) {
        updateProgress(data);
    });
    socket.on('agent_complete', function(data) {
        localStorage.setItem('agentRunning', 'false');
        updateAgentStatus();
    });
}

function appendLog(message, level) {
    var logArea = document.getElementById('logArea');
    var logEntry = document.createElement('div');
    logEntry.textContent = message;
    if (level === 'ERROR') {
        logEntry.style.color = document.body.classList.contains('dark-mode') ? '#ff6b6b' : '#dc3545';
    } else if (level === 'WARNING') {
        logEntry.style.color = document.body.classList.contains('dark-mode') ? '#ffc107' : '#ffc107';
    }
    logArea.appendChild(logEntry);
    logArea.scrollTop = logArea.scrollHeight;
    var logs = JSON.parse(localStorage.getItem('logs') || '[]');
    logs.push({message: message, level: level});
    if (logs.length > 500) logs.shift();
    localStorage.setItem('logs', JSON.stringify(logs));
}

function updateProgress(data) {
    var progressBar = document.getElementById('progressBar');
    var progressBarContainer = document.getElementById('progressBarContainer');
    var progressInfo = document.getElementById('progressInfo');
    var processedCount = document.getElementById('processedCount');
    var totalCount = document.getElementById('totalCount');
    var errorCount = document.getElementById('errorCount');
    var percentage = data.total > 0 ? (data.processed / data.total) * 100 : 0;
    progressBar.style.width = percentage + '%';
    progressBar.setAttribute('aria-valuenow', percentage);
    processedCount.textContent = data.processed;
    totalCount.textContent = data.total;
    errorCount.textContent = data.errors;
    progressBarContainer.style.display = 'block';
    progressInfo.style.display = 'block';
}

function loadCheckboxStates() {
    const checkboxes = ['fetchBookmarks', 'processTweets', 'gitPush'];
    checkboxes.forEach(checkboxId => {
        const savedState = localStorage.getItem(checkboxId);
        if (savedState !== null) {
            document.getElementById(checkboxId).checked = savedState === 'true';
        }
        document.getElementById(checkboxId).addEventListener('change', function() {
            localStorage.setItem(checkboxId, this.checked);
        });
    });
}

function updateAgentStatus() {
    const startButton = document.getElementById('startButton');
    const agentStatus = document.getElementById('agentStatus');
    const isRunning = localStorage.getItem('agentRunning') === 'true';
    if (isRunning) {
        startButton.disabled = true;
        startButton.classList.add('disabled');
        agentStatus.style.display = 'inline';
    } else {
        startButton.disabled = false;
        startButton.classList.remove('disabled');
        agentStatus.style.display = 'none';
    }
}

document.getElementById('controlForm').addEventListener('submit', function(e) {
    localStorage.setItem('agentRunning', 'true');
    updateAgentStatus();
}); 