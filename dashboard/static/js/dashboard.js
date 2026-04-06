/**
 * PilotSuite Styx - Dashboard Tab Logic & WebSocket Connection
 * Material Design Dashboard mit 10 Habituszonen-Tabs
 */

class HabitusDashboard {
    constructor() {
        // Habituszonen Konfiguration
        this.zones = [
            { id: 'wohn', name: 'Wohnbereich', icon: 'mdi-sofa', alertCount: 0 },
            { id: 'bad', name: 'Badbereich', icon: 'mdi-shower', alertCount: 0 },
            { id: 'koch', name: 'Kochbereich', icon: 'mdi-stove', alertCount: 0 },
            { id: 'buero', name: 'Bürobereich', icon: 'mdi-desk', alertCount: 0 },
            { id: 'gang', name: 'Gangbereich', icon: 'mdi-door-open', alertCount: 0 },
            { id: 'schlaf', name: 'Schlafbereich', icon: 'mdi-bed', alertCount: 0 },
            { id: 'mira', name: 'Zimmer Mira', icon: 'mdi-account-girl', alertCount: 0 },
            { id: 'paul', name: 'Zimmer Paul', icon: 'mdi-account-boy', alertCount: 0 },
            { id: 'terrasse', name: 'Terrassenbereich', icon: 'mdi-patio-grass', alertCount: 0 },
            { id: 'aussen', name: 'Aussenbereich', icon: 'mdi-tree', alertCount: 0 }
        ];
        
        this.socket = null;
        this.connected = false;
        this.activeTab = 'wohn';
        this.zoneData = {};
        this.theme = 'light';
        
        this.init();
    }
    
    init() {
        console.log('[Dashboard] Initializing Habitus Dashboard...');
        this.setupTheme();
        this.renderTabs();
        this.renderTabContent();
        this.setupTabNavigation();
        this.setupScrollButtons();
        this.setupWebSocket();
        this.setupThemeToggle();
        this.updateScrollButtons();
        
        // Auto-hide loading after 3 seconds (simulated HA discovery)
        setTimeout(() => {
            this.hideLoading();
        }, 3000);
    }
    
    setupTheme() {
        // Check for HA theme preference or system preference
        const savedTheme = localStorage.getItem('dashboard-theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme) {
            this.theme = savedTheme;
        } else if (systemPrefersDark) {
            this.theme = 'dark';
        }
        
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeIcon();
    }
    
    setupThemeToggle() {
        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                this.theme = this.theme === 'light' ? 'dark' : 'light';
                document.documentElement.setAttribute('data-theme', this.theme);
                localStorage.setItem('dashboard-theme', this.theme);
                this.updateThemeIcon();
            });
        }
    }
    
    updateThemeIcon() {
        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (this.theme === 'dark') {
                icon.className = 'mdi mdi-brightness-7';
            } else {
                icon.className = 'mdi mdi-brightness-auto';
            }
        }
    }
    
    renderTabs() {
        const container = document.getElementById('tabs-container');
        if (!container) return;
        
        container.innerHTML = this.zones.map((zone, index) => `
            <button class="tab-item ${index === 0 ? 'active' : ''}" 
                    data-zone="${zone.id}"
                    onclick="dashboard.switchTab('${zone.id}')">
                <i class="mdi ${zone.icon}"></i>
                <span class="label">${zone.name}</span>
                <span class="badge" id="badge-${zone.id}" style="display: none;">0</span>
            </button>
        `).join('');
    }
    
    renderTabContent() {
        const wrapper = document.getElementById('tab-content-wrapper');
        if (!wrapper) return;
        
        wrapper.innerHTML = this.zones.map((zone, index) => `
            <div class="tab-pane ${index === 0 ? 'active' : ''}" id="pane-${zone.id}">
                <div class="tab-pane-header">
                    <h2><i class="mdi ${zone.icon}"></i> ${zone.name}</h2>
                    <p>Übersicht und Steuerung für ${zone.name.toLowerCase()}</p>
                </div>
                <div class="zone-grid" id="grid-${zone.id}">
                    <div class="empty-state">
                        <i class="mdi ${zone.icon}"></i>
                        <h3>${zone.name} wird geladen...</h3>
                        <p>Home Assistant Discovery läuft</p>
                    </div>
                </div>
                <div class="quick-actions" id="actions-${zone.id}">
                    <button class="quick-action-btn" onclick="dashboard.refreshZone('${zone.id}')">
                        <i class="mdi mdi-refresh"></i> Aktualisieren
                    </button>
                    <button class="quick-action-btn" onclick="dashboard.showZoneSettings('${zone.id}')">
                        <i class="mdi mdi-cog"></i> Einstellungen
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    setupTabNavigation() {
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                const currentIndex = this.zones.findIndex(z => z.id === this.activeTab);
                let newIndex = currentIndex;
                
                if (e.key === 'ArrowLeft' && currentIndex > 0) {
                    newIndex = currentIndex - 1;
                } else if (e.key === 'ArrowRight' && currentIndex < this.zones.length - 1) {
                    newIndex = currentIndex + 1;
                }
                
                if (newIndex !== currentIndex) {
                    this.switchTab(this.zones[newIndex].id);
                }
            }
        });
    }
    
    setupScrollButtons() {
        const scrollLeft = document.getElementById('scroll-left');
        const scrollRight = document.getElementById('scroll-right');
        const container = document.getElementById('tabs-container');
        
        if (scrollLeft && scrollRight && container) {
            scrollLeft.addEventListener('click', () => {
                container.scrollBy({ left: -200, behavior: 'smooth' });
            });
            
            scrollRight.addEventListener('click', () => {
                container.scrollBy({ left: 200, behavior: 'smooth' });
            });
            
            container.addEventListener('scroll', () => {
                this.updateScrollButtons();
            });
        }
    }
    
    updateScrollButtons() {
        const scrollLeft = document.getElementById('scroll-left');
        const scrollRight = document.getElementById('scroll-right');
        const container = document.getElementById('tabs-container');
        
        if (scrollLeft && scrollRight && container) {
            scrollLeft.disabled = container.scrollLeft === 0;
            scrollRight.disabled = container.scrollLeft + container.clientWidth >= container.scrollWidth - 1;
        }
    }
    
    switchTab(zoneId) {
        if (this.activeTab === zoneId) return;
        
        this.activeTab = zoneId;
        
        // Update tab buttons
        document.querySelectorAll('.tab-item').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.zone === zoneId);
        });
        
        // Update tab panes
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `pane-${zoneId}`);
        });
        
        // Scroll active tab into view
        const activeTab = document.querySelector(`.tab-item[data-zone="${zoneId}"]`);
        if (activeTab) {
            activeTab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
        
        this.updateLastUpdateTime();
        console.log(`[Dashboard] Switched to tab: ${zoneId}`);
    }
    
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}`;
        
        console.log('[Dashboard] Connecting to WebSocket:', wsUrl);
        
        this.socket = io(wsUrl, {
            transports: ['websocket', 'polling'],
            upgrade: true,
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 10
        });
        
        this.socket.on('connect', () => {
            this.connected = true;
            this.updateConnectionStatus('connected');
            console.log('[Dashboard] WebSocket connected');
            
            // Request zone data
            this.socket.emit('request_zone_data', { zones: this.zones.map(z => z.id) });
        });
        
        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            this.updateConnectionStatus('disconnected');
            console.log('[Dashboard] WebSocket disconnected:', reason);
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('[Dashboard] WebSocket connection error:', error);
        });
        
        this.socket.on('zone_update', (data) => {
            this.handleZoneUpdate(data);
        });
        
        this.socket.on('alert_update', (data) => {
            this.handleAlertUpdate(data);
        });
        
        this.socket.on('ha_discovery_complete', (data) => {
            this.hideLoading();
            this.loadZoneData();
            console.log('[Dashboard] HA Discovery complete');
        });
    }
    
    updateConnectionStatus(status) {
        const indicator = document.getElementById('connection-indicator');
        const statusText = document.getElementById('connection-status');
        
        if (indicator && statusText) {
            indicator.className = `status-indicator ${status}`;
            statusText.textContent = status === 'connected' ? 'Verbunden' : 'Getrennt';
        }
    }
    
    handleZoneUpdate(data) {
        if (!data.zoneId || !data.data) return;
        
        this.zoneData[data.zoneId] = data.data;
        this.renderZoneCards(data.zoneId);
        this.updateLastUpdateTime();
    }
    
    handleAlertUpdate(data) {
        if (!data.zoneId || typeof data.alertCount !== 'number') return;
        
        const zone = this.zones.find(z => z.id === data.zoneId);
        if (zone) {
            zone.alertCount = data.alertCount;
            this.updateAlertBadge(data.zoneId, data.alertCount);
            this.updateTotalAlerts();
        }
    }
    
    updateAlertBadge(zoneId, count) {
        const badge = document.getElementById(`badge-${zoneId}`);
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 9 ? '9+' : count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    }
    
    updateTotalAlerts() {
        const total = this.zones.reduce((sum, z) => sum + z.alertCount, 0);
        const badge = document.getElementById('alert-badge');
        if (badge) {
            badge.textContent = total > 9 ? '9+' : total;
        }
    }
    
    renderZoneCards(zoneId) {
        const grid = document.getElementById(`grid-${zoneId}`);
        if (!grid || !this.zoneData[zoneId]) return;
        
        const data = this.zoneData[zoneId];
        
        // Beispielhafte Darstellung (wird durch echte HA-Daten ersetzt)
        grid.innerHTML = `
            <div class="zone-card widget-container" data-widget-id="temp-${zoneId}" data-x="0" data-y="0">
                <div class="drag-handle" title="Zum Verschieben ziehen">
                    <i class="mdi mdi-drag"></i>
                </div>
                <div class="position-controls">
                    <button class="position-btn" onclick="dragDropManager.undo()" title="Rückgängig (Strg+Z)">
                        <i class="mdi mdi-undo"></i>
                    </button>
                    <button class="position-btn" onclick="dragDropManager.redo()" title="Wiederherstellen (Strg+Y)">
                        <i class="mdi mdi-redo"></i>
                    </button>
                </div>
                <div class="zone-card-header">
                    <div class="zone-card-icon">
                        <i class="mdi mdi-thermometer"></i>
                    </div>
                    <div class="zone-card-status">
                        <span class="status-dot"></span>
                        <span>Aktiv</span>
                    </div>
                </div>
                <div class="zone-card-title">Temperatur</div>
                <div class="zone-card-subtitle">Durchschnittswert</div>
                <div class="zone-card-metrics">
                    <div class="zone-metric">
                        <span class="zone-metric-label">Aktuell</span>
                        <span class="zone-metric-value">${data.temperature || '21.5'}°C</span>
                    </div>
                    <div class="zone-metric">
                        <span class="zone-metric-label">Ziel</span>
                        <span class="zone-metric-value">${data.targetTemp || '22.0'}°C</span>
                    </div>
                </div>
            </div>
            
            <div class="zone-card widget-container" data-widget-id="humidity-${zoneId}" data-x="0" data-y="0">
                <div class="drag-handle" title="Zum Verschieben ziehen">
                    <i class="mdi mdi-drag"></i>
                </div>
                <div class="position-controls">
                    <button class="position-btn" onclick="dragDropManager.undo()" title="Rückgängig (Strg+Z)">
                        <i class="mdi mdi-undo"></i>
                    </button>
                    <button class="position-btn" onclick="dragDropManager.redo()" title="Wiederherstellen (Strg+Y)">
                        <i class="mdi mdi-redo"></i>
                    </button>
                </div>
                <div class="zone-card-header">
                    <div class="zone-card-icon">
                        <i class="mdi mdi-water-percent"></i>
                    </div>
                    <div class="zone-card-status">
                        <span class="status-dot"></span>
                        <span>Aktiv</span>
                    </div>
                </div>
                <div class="zone-card-title">Luftfeuchtigkeit</div>
                <div class="zone-card-subtitle">Relative Feuchte</div>
                <div class="zone-card-metrics">
                    <div class="zone-metric">
                        <span class="zone-metric-label">Aktuell</span>
                        <span class="zone-metric-value">${data.humidity || '45'}%</span>
                    </div>
                    <div class="zone-metric">
                        <span class="zone-metric-label">Bereich</span>
                        <span class="zone-metric-value">40-60%</span>
                    </div>
                </div>
            </div>
            
            <div class="zone-card widget-container" data-widget-id="lights-${zoneId}" data-x="0" data-y="0">
                <div class="drag-handle" title="Zum Verschieben ziehen">
                    <i class="mdi mdi-drag"></i>
                </div>
                <div class="position-controls">
                    <button class="position-btn" onclick="dragDropManager.undo()" title="Rückgängig (Strg+Z)">
                        <i class="mdi mdi-undo"></i>
                    </button>
                    <button class="position-btn" onclick="dragDropManager.redo()" title="Wiederherstellen (Strg+Y)">
                        <i class="mdi mdi-redo"></i>
                    </button>
                </div>
                <div class="zone-card-header">
                    <div class="zone-card-icon">
                        <i class="mdi mdi-lightbulb"></i>
                    </div>
                    <div class="zone-card-status">
                        <span class="status-dot"></span>
                        <span>Aktiv</span>
                    </div>
                </div>
                <div class="zone-card-title">Beleuchtung</div>
                <div class="zone-card-subtitle">Aktive Lichter</div>
                <div class="zone-card-metrics">
                    <div class="zone-metric">
                        <span class="zone-metric-label">Anzahl</span>
                        <span class="zone-metric-value">${data.lights || '3'}</span>
                    </div>
                    <div class="zone-metric">
                        <span class="zone-metric-label">Helligkeit</span>
                        <span class="zone-metric-value">${data.brightness || '60'}%</span>
                    </div>
                </div>
            </div>
        `;
        
        // Drag & Drop für neue Cards aktivieren
        if (window.dragDropManager) {
            window.dragDropManager.enableDrag(`#grid-${zoneId} .widget-container`);
        }
    }
    
    loadZoneData() {
        // Simuliertes Laden von Zonendaten (wird durch echte API ersetzt)
        this.zones.forEach(zone => {
            this.zoneData[zone.id] = {
                temperature: (20 + Math.random() * 3).toFixed(1),
                targetTemp: (21 + Math.random() * 2).toFixed(1),
                humidity: Math.floor(40 + Math.random() * 20),
                lights: Math.floor(Math.random() * 5),
                brightness: Math.floor(40 + Math.random() * 40)
            };
            this.renderZoneCards(zone.id);
        });
    }
    
    refreshZone(zoneId) {
        console.log(`[Dashboard] Refreshing zone: ${zoneId}`);
        if (this.socket && this.connected) {
            this.socket.emit('request_zone_data', { zones: [zoneId] });
        }
    }
    
    showZoneSettings(zoneId) {
        console.log(`[Dashboard] Opening settings for zone: ${zoneId}`);
        // Hier könnte ein Modal oder eine separate Einstellungsseite geöffnet werden
        alert(`Einstellungen für ${zoneId} werden geöffnet...`);
    }
    
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }
    
    updateLastUpdateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('de-DE');
        const element = document.getElementById('last-update-time');
        if (element) {
            element.textContent = timeString;
        }
    }
}

// Dashboard initialisieren
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new HabitusDashboard();
});

// Export für globalen Zugriff
window.dashboard = dashboard;


// ── Brain Graph Integration (P3-003) ──────────────────────────────────────────
HabitusDashboard.prototype.initBrainGraph = function() {
    // Load brain graph visualization when tab becomes active
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                const activePane = document.querySelector('.tab-pane.active');
                if (activePane && activePane.id === 'pane-brain') {
                    this.loadBrainGraph();
                }
            }
        });
    });

    const tabsContainer = document.querySelector('.tabs-container');
    if (tabsContainer) {
        observer.observe(tabsContainer, { attributes: true, subtree: true });
    }

    // Also add brain tab to zones
    this.zones.push({
        id: 'brain',
        name: 'Brain Graph',
        icon: 'mdi-brain',
        alertCount: 0
    });
};

HabitusDashboard.prototype.loadBrainGraph = function() {
    if (this._brainGraphLoaded) return;
    this._brainGraphLoaded = true;

    fetch('/api/v1/backend/brain/graph/state?limit_nodes=30&limit_edges=60')
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (!data) return;
            this._brainGraphData = data;
            this.renderBrainGraphWidget();
        })
        .catch(() => {});
};

HabitusDashboard.prototype.renderBrainGraphWidget = function() {
    const data = this._brainGraphData;
    if (!data) return;

    let html = '<div class="zone-card widget-container" style="grid-column: 1/-1;">';
    html += '<div class="zone-card-header"><div class="zone-card-icon"><i class="mdi mdi-brain"></i></div>';
    html += '<div class="zone-card-status"><span class="status-dot active"></span><span>Active</span></div></div>';
    html += '<div class="zone-card-title">Brain Graph</div>';
    html += '<div class="zone-card-subtitle">Nodes: ' + (data.nodes ? data.nodes.length : 0) + ' | Edges: ' + (data.edges ? data.edges.length : 0) + '</div>';
    html += '<div class="zone-card-metrics">';
    if (data.nodes) {
        data.nodes.slice(0, 5).forEach(n => {
            html += '<div class="zone-metric"><span class="zone-metric-label">' + (n.label || n.id || '?') + '</span><span class="zone-metric-value">' + (n.type || 'node') + '</span></div>';
        });
    }
    html += '</div></div>';
    html += '</div>';

    const pane = document.getElementById('pane-brain');
    if (pane) {
        const grid = pane.querySelector('.zone-grid');
        if (grid) grid.innerHTML = html;
    }
};

// Anomaly widget (P3-005)
window.addEventListener('DOMContentLoaded', () => {
    const el = document.createElement('div');
    el.id = 'anomaly-widgets';
    el.style.cssText = 'position:fixed;bottom:60px;right:24px;width:280px;z-index:200;display:flex;flex-direction:column;gap:6px;';
    const footer = document.querySelector('.dashboard-footer');
    if (footer) footer.parentElement.insertBefore(el, footer);
    fetch('/api/v1/anomaly/history?limit=5').then(r => r.ok ? r.json() : {anomalies:[]}).then(d => {
        const c = document.getElementById('anomaly-widgets');
        if (!c || !d.anomalies) return;
        const m = {low:'#4caf50',medium:'#ff9800',high:'#f44336',critical:'#9c27b0'};
        c.innerHTML = d.anomalies.slice(0,3).map(a =>
            '<div style="background:#1e1e2e;border-left:3px solid '+(m[a.severity]||'#9e9e9e')+';padding:6px 10px;border-radius:4px;font-size:11px;color:#e0e0e0">'
            +'<b>'+(a.anomaly_type||'?')+'</b> '+((a.zone_id)||'')+'<br><span style="color:#9e9e9e">'+(a.description||'')+'</span></div>'
        ).join('');
    }).catch(() => {});
});
