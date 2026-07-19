// Tab navigation
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.dataset.tab;

        // Hide all sections
        document.querySelectorAll('.tab-section').forEach(section => {
            section.classList.remove('active');
        });

        // Remove active from all buttons
        document.querySelectorAll('.tab-btn').forEach(b => {
            b.classList.remove('active');
        });

        // Show selected section and mark button as active
        document.getElementById(tabId).classList.add('active');
        btn.classList.add('active');

        // Load data for the tab
        if (tabId === 'leads-tab') {
            loadLeads();
        } else if (tabId === 'logs-tab') {
            loadCallLogs();
        } else if (tabId === 'settings-tab') {
            loadSystemInfo();
        }
    });
});

// Load initial data
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadLeads();
    checkApiKey();

    // Setup dialer controls
    setupDialerControls();

    // Refresh stats every 30 seconds
    setInterval(loadStats, 30000);

    // Check dialer status every 5 seconds
    setInterval(checkDialerStatus, 5000);
    checkDialerStatus(); // Check immediately
});

// Search and filter functionality
document.getElementById('search-leads')?.addEventListener('input', filterLeads);
document.getElementById('filter-status')?.addEventListener('change', filterLeads);
document.getElementById('search-logs')?.addEventListener('input', filterLogs);
document.getElementById('filter-disposition')?.addEventListener('change', filterLogs);

// Load and display stats
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        document.getElementById('total-leads').textContent = data.total_leads;
        document.getElementById('pending-leads').textContent = data.pending_leads;
        document.getElementById('completed-calls').textContent = data.completed_calls;
        document.getElementById('avg-motivation').textContent = data.avg_motivation + '/100';
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load and display leads
async function loadLeads() {
    try {
        const response = await fetch('/api/leads');
        const data = await response.json();

        const tbody = document.getElementById('leads-body');

        if (!data.leads || data.leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No leads found. Run the skip tracer to populate.</td></tr>';
            return;
        }

        window.leadsData = data.leads; // Store for filtering
        renderLeads(data.leads);
    } catch (error) {
        console.error('Error loading leads:', error);
        document.getElementById('leads-body').innerHTML = '<tr><td colspan="6" class="loading">Error loading leads</td></tr>';
    }
}

function renderLeads(leads) {
    const tbody = document.getElementById('leads-body');
    tbody.innerHTML = leads.map(lead => `
        <tr>
            <td><strong>${lead.owner}</strong></td>
            <td>${lead.property}</td>
            <td>${lead.phone_1}</td>
            <td><span class="score ${getScoreClass(lead.motivation_score)}">${lead.motivation_score}</span></td>
            <td><span class="badge ${lead.call_status}">${lead.call_status}</span></td>
            <td>${formatDate(lead.traced_at)}</td>
        </tr>
    `).join('');
}

// Filter leads
function filterLeads() {
    if (!window.leadsData) return;

    const searchText = (document.getElementById('search-leads')?.value || '').toLowerCase();
    const statusFilter = document.getElementById('filter-status')?.value || '';

    const filtered = window.leadsData.filter(lead => {
        const matchesSearch = !searchText ||
            lead.owner.toLowerCase().includes(searchText) ||
            lead.property.toLowerCase().includes(searchText) ||
            lead.phone_1.includes(searchText);

        const matchesStatus = !statusFilter || lead.call_status === statusFilter;

        return matchesSearch && matchesStatus;
    });

    renderLeads(filtered);
}

// Load and display call logs
async function loadCallLogs() {
    try {
        const response = await fetch('/api/call-logs');
        const data = await response.json();

        const tbody = document.getElementById('logs-body');

        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No call logs yet. Start dialing to see results.</td></tr>';
            return;
        }

        window.logsData = data.logs; // Store for filtering
        renderLogs(data.logs);
    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('logs-body').innerHTML = '<tr><td colspan="6" class="loading">Error loading call logs</td></tr>';
    }
}

function renderLogs(logs) {
    const tbody = document.getElementById('logs-body');
    tbody.innerHTML = logs.map(log => `
        <tr>
            <td>${formatDate(log.timestamp)}</td>
            <td><strong>${log.owner}</strong></td>
            <td>${log.property}</td>
            <td><span class="badge ${log.disposition}">${log.disposition}</span></td>
            <td>${log.motivation || '-'}</td>
            <td title="${log.summary}">${truncate(log.summary, 40)}</td>
        </tr>
    `).join('');
}

// Filter logs
function filterLogs() {
    if (!window.logsData) return;

    const searchText = (document.getElementById('search-logs')?.value || '').toLowerCase();
    const dispositionFilter = document.getElementById('filter-disposition')?.value || '';

    const filtered = window.logsData.filter(log => {
        const matchesSearch = !searchText ||
            log.owner.toLowerCase().includes(searchText) ||
            log.property.toLowerCase().includes(searchText) ||
            log.phone.includes(searchText);

        const matchesDisposition = !dispositionFilter || log.disposition === dispositionFilter;

        return matchesSearch && matchesDisposition;
    });

    renderLogs(filtered);
}

// Check API key status
async function checkApiKey() {
    try {
        const response = await fetch('/api/check-api-key');
        const data = await response.json();

        const statusEl = document.getElementById('api-status');
        if (data.configured) {
            statusEl.classList.add('ready');
            statusEl.innerHTML = '<span class="dot"></span>Ready to dial';
        } else {
            statusEl.innerHTML = '<span class="dot"></span>API key not configured';
        }
    } catch (error) {
        console.error('Error checking API key:', error);
    }
}

// Load system info
async function loadSystemInfo() {
    try {
        const response = await fetch('/api/system-info');
        const data = await response.json();

        const statusEl = document.getElementById('api-key-status');
        if (data.api_configured) {
            statusEl.textContent = '✓ Configured';
            statusEl.classList.add('ready');
        } else {
            statusEl.textContent = 'Not configured';
        }

        const dirEl = document.getElementById('data-dir');
        if (dirEl) dirEl.textContent = data.data_dir;
    } catch (error) {
        console.error('Error loading system info:', error);
    }
}

// Dialer controls
function setupDialerControls() {
    const startBtn = document.getElementById('start-dialer-btn');
    const stopBtn = document.getElementById('stop-dialer-btn');

    if (startBtn) {
        startBtn.addEventListener('click', startDialer);
    }
    if (stopBtn) {
        stopBtn.addEventListener('click', stopDialer);
    }
}

async function startDialer() {
    try {
        const response = await fetch('/api/start-dialer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        updateDialerStatus(true);
        alert('✅ Dialer started! View results in the Calls tab.');
    } catch (error) {
        console.error('Error starting dialer:', error);
        alert('Failed to start dialer');
    }
}

async function stopDialer() {
    try {
        const response = await fetch('/api/stop-dialer', { method: 'POST' });
        const data = await response.json();
        updateDialerStatus(false);
    } catch (error) {
        console.error('Error stopping dialer:', error);
    }
}

async function checkDialerStatus() {
    try {
        const response = await fetch('/api/dialer-status');
        const data = await response.json();
        updateDialerStatus(data.running);
    } catch (error) {
        console.error('Error checking dialer status:', error);
    }
}

function updateDialerStatus(running) {
    const startBtn = document.getElementById('start-dialer-btn');
    const stopBtn = document.getElementById('stop-dialer-btn');
    const indicator = document.getElementById('dialer-indicator');

    if (running) {
        if (startBtn) startBtn.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'block';
        if (indicator) {
            indicator.textContent = '🟢 Running';
            indicator.classList.add('running');
        }
        // Refresh logs when dialer is running
        if (document.getElementById('logs-tab').classList.contains('active')) {
            loadCallLogs();
        }
    } else {
        if (startBtn) startBtn.style.display = 'block';
        if (stopBtn) stopBtn.style.display = 'none';
        if (indicator) {
            indicator.textContent = '⚫ Idle';
            indicator.classList.remove('running');
        }
    }
}

// Utility functions
function getScoreClass(score) {
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    } catch {
        return dateStr;
    }
}

function truncate(str, len) {
    if (!str) return '-';
    return str.length > len ? str.substring(0, len) + '...' : str;
}
