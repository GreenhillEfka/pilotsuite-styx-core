/**
 * Zone Dashboard Component - PilotSuite Dashboard
 * 
 * Lit-based Web Component for zone overview dashboard:
 * - Grid layout with zone cards
 * - Real-time status (active, idle, persons)
 * - Mood visualization (comfort, joy, frugality)
 * - Entity count per zone
 * - Quick actions (toggle zone, change mood)
 * 
 * Integration:
 * - Reuses zone_editor.js styles and patterns
 * - Dashboard view (read-only, fast)
 * - Links to zone_editor for full editing
 * 
 * Author: Clawdya (via Codex)
 * Version: 1.0.0
 */

import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

// API Base URL
const API_BASE = '/api/v1/zone/dashboard';

// Status colors
const STATUS_COLORS = {
  active: '#4CAF50',      // Green
  idle: '#9E9E9E',        // Grey
  disabled: '#F44336',    // Red
  transitioning: '#FF9800', // Orange
};

// Status icons
const STATUS_ICONS = {
  active: 'mdi:motion-sensor',
  idle: 'mdi:sleep',
  disabled: 'mdi:cancel',
  transitioning: 'mdi:sync',
};

/**
 * ZoneDashboardComponent
 * 
 * Main zone dashboard UI with grid overview, status, mood, and quick actions.
 */
@customElement('zone-dashboard')
export class ZoneDashboardComponent extends LitElement {
  static styles = css`
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      padding: 16px;
      background: #f5f5f5;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }

    .header h2 {
      margin: 0;
      color: #1a1a1a;
      font-size: 24px;
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }

    .btn {
      padding: 8px 16px;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .btn-primary {
      background: #007bff;
      color: white;
    }

    .btn-primary:hover {
      background: #0056b3;
    }

    .btn-secondary {
      background: #6c757d;
      color: white;
    }

    .btn-secondary:hover {
      background: #545b62;
    }

    .btn-success {
      background: #28a745;
      color: white;
    }

    .btn-success:hover {
      background: #218838;
    }

    .btn-sm {
      padding: 4px 8px;
      font-size: 12px;
    }

    /* Summary Cards */
    .summary-bar {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .summary-card {
      background: white;
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.05);
      text-align: center;
    }

    .summary-value {
      font-size: 28px;
      font-weight: 700;
      color: #007bff;
      margin-bottom: 4px;
    }

    .summary-label {
      font-size: 12px;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    /* Zone Grid */
    .zone-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 20px;
    }

    .zone-card {
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      transition: all 0.2s;
      border: 2px solid transparent;
    }

    .zone-card:hover {
      box-shadow: 0 4px 16px rgba(0,0,0,0.12);
      transform: translateY(-2px);
    }

    .zone-card.active {
      border-color: #4CAF50;
    }

    .zone-card.idle {
      border-color: #e0e0e0;
    }

    .zone-card.disabled {
      border-color: #F44336;
      opacity: 0.7;
    }

    .zone-header {
      padding: 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid #f0f0f0;
    }

    .zone-status-icon {
      font-size: 24px;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #f5f5f5;
    }

    .zone-card.active .zone-status-icon {
      background: #E8F5E9;
      color: #4CAF50;
    }

    .zone-name {
      font-size: 18px;
      font-weight: 600;
      color: #1a1a1a;
      flex: 1;
    }

    .zone-badge {
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }

    .badge-active {
      background: #E8F5E9;
      color: #2E7D32;
    }

    .badge-idle {
      background: #F5F5F5;
      color: #616161;
    }

    .badge-disabled {
      background: #FFEBEE;
      color: #C62828;
    }

    .zone-body {
      padding: 16px;
    }

    /* Mood Bars */
    .mood-section {
      margin-bottom: 16px;
    }

    .mood-label {
      font-size: 12px;
      color: #666;
      margin-bottom: 6px;
      display: flex;
      justify-content: space-between;
    }

    .mood-bar-container {
      height: 8px;
      background: #f0f0f0;
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 8px;
    }

    .mood-bar {
      height: 100%;
      border-radius: 4px;
      transition: width 0.3s ease;
    }

    .mood-comfort {
      background: linear-gradient(90deg, #64B5F6, #1976D2);
    }

    .mood-joy {
      background: linear-gradient(90deg, #FFD54F, #FF8F00);
    }

    .mood-frugality {
      background: linear-gradient(90deg, #81C784, #388E3C);
    }

    /* Entity Count */
    .entity-stats {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;
      padding: 12px;
      background: #f9f9f9;
      border-radius: 8px;
    }

    .stat-item {
      text-align: center;
    }

    .stat-value {
      font-size: 20px;
      font-weight: 700;
      color: #333;
    }

    .stat-label {
      font-size: 10px;
      color: #666;
      text-transform: uppercase;
    }

    /* Quick Actions */
    .quick-actions {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
    }

    .action-btn {
      padding: 8px 12px;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      background: white;
      cursor: pointer;
      font-size: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s;
    }

    .action-btn:hover {
      background: #007bff;
      color: white;
      border-color: #007bff;
    }

    .action-btn:active {
      transform: scale(0.98);
    }

    /* Loading & Error States */
    .loading {
      text-align: center;
      padding: 48px;
      color: #666;
    }

    .loading-spinner {
      display: inline-block;
      width: 40px;
      height: 40px;
      border: 4px solid #f0f0f0;
      border-top-color: #007bff;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin-bottom: 16px;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .error-message {
      background: #ffebee;
      color: #c62828;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 16px;
    }

    .empty-state {
      text-align: center;
      padding: 48px 24px;
      color: #666;
    }

    .empty-state-icon {
      font-size: 48px;
      margin-bottom: 16px;
      opacity: 0.5;
    }

    /* Refresh indicator */
    .refresh-indicator {
      position: fixed;
      top: 16px;
      right: 16px;
      background: white;
      padding: 8px 12px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      font-size: 12px;
      color: #666;
      display: flex;
      align-items: center;
      gap: 8px;
      z-index: 100;
    }

    .refresh-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #4CAF50;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
  `;

  @property({ type: Array })
  zones = [];

  @property({ type: Boolean })
  loading = true;

  @property({ type: String })
  error = null;

  @property({ type: Object })
  summary = null;

  @state()
  lastUpdated = null;

  @state()
  autoRefresh = true;

  @state()
  refreshInterval = null;

  async firstUpdated() {
    await this.loadDashboard();
    this.startAutoRefresh();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.stopAutoRefresh();
  }

  startAutoRefresh() {
    if (this.autoRefresh) {
      this.refreshInterval = setInterval(() => {
        this.loadDashboard(true);
      }, 30000); // Refresh every 30 seconds
    }
  }

  stopAutoRefresh() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }

  async loadDashboard(silent = false) {
    if (!silent) {
      this.loading = true;
    }
    this.error = null;
    
    try {
      const [dashboardResponse, summaryResponse] = await Promise.all([
        fetch(`${API_BASE}?include_entities=false&include_mood=true&include_actions=true`, {
          headers: this._getAuthHeaders(),
        }),
        fetch(`${API_BASE}/summary`, {
          headers: this._getAuthHeaders(),
        }),
      ]);
      
      if (!dashboardResponse.ok) {
        throw new Error(`Dashboard: HTTP ${dashboardResponse.status}`);
      }
      
      if (!summaryResponse.ok) {
        throw new Error(`Summary: HTTP ${summaryResponse.status}`);
      }
      
      const dashboardData = await dashboardResponse.json();
      const summaryData = await summaryResponse.json();
      
      this.zones = dashboardData.zones || [];
      this.summary = summaryData.summary || null;
      this.lastUpdated = new Date().toLocaleTimeString();
    } catch (err) {
      this.error = `Failed to load dashboard: ${err.message}`;
      console.error('Dashboard load error:', err);
    } finally {
      this.loading = false;
    }
  }

  _getAuthHeaders() {
    const token = localStorage.getItem('pilotsuite_token') || 
                  document.cookie.split('; ').find(row => row.startsWith('auth_token='))?.split('=')[1];
    
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Auth-Token': token } : {}),
    };
  }

  async _executeQuickAction(zoneId, action) {
    try {
      const response = await fetch(`${API_BASE}/quick-action`, {
        method: 'POST',
        headers: this._getAuthHeaders(),
        body: JSON.stringify({
          zone_id: zoneId,
          action_id: action.action_id,
          service: action.service,
          target: action.target,
          data: action.data,
        }),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Action failed');
      }
      
      // Show success feedback
      this._showToast(`Action executed: ${action.name}`);
      
      // Refresh dashboard
      await this.loadDashboard(true);
    } catch (err) {
      console.error('Quick action error:', err);
      this._showToast(`Error: ${err.message}`, 'error');
    }
  }

  _showToast(message, type = 'success') {
    // Simple toast notification (could be enhanced with a proper toast component)
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: ${type === 'error' ? '#F44336' : '#4CAF50'};
      color: white;
      padding: 12px 24px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 1000;
      animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }

  _getStatusColor(status) {
    return STATUS_COLORS[status] || STATUS_COLORS.idle;
  }

  _getStatusIcon(status) {
    return STATUS_ICONS[status] || STATUS_ICONS.idle;
  }

  _getBadgeClass(status) {
    if (status === 'active') return 'badge-active';
    if (status === 'disabled') return 'badge-disabled';
    return 'badge-idle';
  }

  _renderSummaryBar() {
    if (!this.summary) return null;
    
    return html`
      <div class="summary-bar">
        <div class="summary-card">
          <div class="summary-value">${this.summary.total_zones}</div>
          <div class="summary-label">Zonen</div>
        </div>
        <div class="summary-card">
          <div class="summary-value" style="color: #4CAF50;">${this.summary.active_zones}</div>
          <div class="summary-label">Aktiv</div>
        </div>
        <div class="summary-card">
          <div class="summary-value" style="color: #9E9E9E;">${this.summary.idle_zones}</div>
          <div class="summary-label">Inaktiv</div>
        </div>
        <div class="summary-card">
          <div class="summary-value" style="color: #FF9800;">${this.summary.total_entities}</div>
          <div class="summary-label">Entitaeten</div>
        </div>
        <div class="summary-card">
          <div class="summary-value" style="color: #2196F3;">${this.summary.total_persons}</div>
          <div class="summary-label">Personen</div>
        </div>
      </div>
    `;
  }

  _renderMoodBar(mood, type) {
    const value = mood?.[type] || 0;
    const percentage = Math.round(value * 100);
    
    const labels = {
      comfort: 'Komfort',
      joy: 'Freude',
      frugality: 'Sparsamkeit',
    };
    
    return html`
      <div class="mood-label">
        <span>${labels[type]}</span>
        <span>${percentage}%</span>
      </div>
      <div class="mood-bar-container">
        <div 
          class="mood-bar mood-${type}" 
          style="width: ${percentage}%;"
        ></div>
      </div>
    `;
  }

  _renderZoneCard(zone) {
    const status = zone.status || 'idle';
    const mood = zone.mood || {};
    const quickActions = zone.quick_actions || [];
    
    return html`
      <div class="zone-card ${status}">
        <div class="zone-header">
          <div class="zone-status-icon" style="color: ${this._getStatusColor(status)};">
            ${this._getStatusIcon(status)}
          </div>
          <span class="zone-name">${zone.name}</span>
          <span class="zone-badge ${this._getBadgeClass(status)}">${status}</span>
        </div>
        
        <div class="zone-body">
          <!-- Mood Section -->
          <div class="mood-section">
            ${this._renderMoodBar(mood, 'comfort')}
            ${this._renderMoodBar(mood, 'joy')}
            ${this._renderMoodBar(mood, 'frugality')}
          </div>
          
          <!-- Entity Stats -->
          <div class="entity-stats">
            <div class="stat-item">
              <div class="stat-value">${zone.entity_count || 0}</div>
              <div class="stat-label">Entities</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">${zone.person_count || 0}</div>
              <div class="stat-label">Personen</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">${Object.keys(zone.entity_counts_by_domain || {}).length}</div>
              <div class="stat-label">Typen</div>
            </div>
          </div>
          
          <!-- Quick Actions -->
          ${quickActions.length > 0 ? html`
            <div class="quick-actions">
              ${quickActions.slice(0, 4).map(action => html`
                <button 
                  class="action-btn"
                  @click=${() => this._executeQuickAction(zone.zone_id, action)}
                  title="${action.name}"
                >
                  <span>${action.icon}</span>
                  <span>${action.name}</span>
                </button>
              `)}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  _renderEditorLink() {
    return html`
      <button class="btn btn-secondary" @click=${() => this._openZoneEditor()}>
        <span>⚙️</span>
        <span>Zone Editor</span>
      </button>
    `;
  }

  _openZoneEditor() {
    // Navigate to zone editor page or open modal
    // In production, this would use router or custom event
    const event = new CustomEvent('open-zone-editor', {
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
    
    // Fallback: direct navigation
    window.location.href = '/dashboard/zone-editor';
  }

  render() {
    return html`
      <div class="header">
        <h2>🏠 Zone Dashboard</h2>
        <div class="header-actions">
          ${this._renderEditorLink()}
          <button class="btn btn-primary" @click=${() => this.loadDashboard()}>
            🔄 Refresh
          </button>
        </div>
      </div>
      
      ${this.lastUpdated ? html`
        <div class="refresh-indicator">
          <div class="refresh-dot"></div>
          <span>Updated: ${this.lastUpdated}</span>
        </div>
      ` : ''}
      
      ${this.loading ? html`
        <div class="loading">
          <div class="loading-spinner"></div>
          <p>Loading dashboard...</p>
        </div>
      ` : this.error ? html`
        <div class="error-message">${this.error}</div>
      ` : this.zones.length === 0 ? html`
        <div class="empty-state">
          <div class="empty-state-icon">🏠</div>
          <p>Keine Zonen vorhanden.</p>
          <button class="btn btn-primary" style="margin-top: 16px;" @click=${() => this._openZoneEditor()}>
            Erste Zone erstellen
          </button>
        </div>
      ` : html`
        ${this._renderSummaryBar()}
        <div class="zone-grid">
          ${this.zones.map(zone => this._renderZoneCard(zone))}
        </div>
      `}
    `;
  }
}

// Export for module usage
export { ZoneDashboardComponent };
