/**
 * Sunrise Alarm Card for Home Assistant Lovelace
 * 
 * Features:
 * - Sunrise/Sunset light ramp visualization
 * - Zone/person-based alarm management
 * - Snooze/Dismiss/Cancel controls
 * - Progress bar during active alarm
 * - Preset quick-select
 * 
 * Usage in Lovelace:
 * type: custom:sunrise-alarm-card
 * entity: sensor.sunrise_alarm_next
 */

class SunriseAlarmCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      this.attachShadow({ mode: 'open' });
      this.content = document.createElement('div');
      this.content.className = 'sunrise-alarm-card';
      this.style.display = 'block';
      this.shadowRoot.appendChild(this.content);
      
      const style = document.createElement('style');
      style.textContent = `
        .sunrise-alarm-card {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          border-radius: 16px;
          padding: 20px;
          color: #e8e8e8;
          box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }
        .card-title {
          font-size: 18px;
          font-weight: 600;
          color: #ffd93d;
        }
        .card-icon {
          font-size: 24px;
        }
        .alarm-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: 400px;
          overflow-y: auto;
        }
        .alarm-item {
          background: rgba(255,255,255,0.05);
          border-radius: 12px;
          padding: 14px;
          border-left: 4px solid #ffd93d;
          transition: all 0.3s ease;
        }
        .alarm-item.ringing {
          border-left-color: #ff6b6b;
          animation: pulse 1.5s infinite;
        }
        .alarm-item.snoozed {
          border-left-color: #feca57;
        }
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(255,107,107,0.4); }
          50% { box-shadow: 0 0 0 8px rgba(255,107,107,0); }
        }
        .alarm-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        .alarm-time {
          font-size: 28px;
          font-weight: 700;
          color: #fff;
        }
        .alarm-label {
          font-size: 14px;
          color: #a8a8a8;
        }
        .alarm-meta {
          display: flex;
          gap: 8px;
          margin-top: 8px;
          flex-wrap: wrap;
        }
        .alarm-badge {
          background: rgba(255,217,61,0.15);
          color: #ffd93d;
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 500;
        }
        .alarm-badge.zone {
          background: rgba(78,205,196,0.15);
          color: #4ecdc4;
        }
        .alarm-badge.person {
          background: rgba(255,107,107,0.15);
          color: #ff6b6b;
        }
        .progress-bar {
          width: 100%;
          height: 6px;
          background: rgba(255,255,255,0.1);
          border-radius: 3px;
          margin-top: 12px;
          overflow: hidden;
        }
        .progress-fill {
          height: 100%;
          background: linear-gradient(90deg, #ff6b6b, #ffd93d);
          border-radius: 3px;
          transition: width 0.5s ease;
        }
        .alarm-actions {
          display: flex;
          gap: 8px;
          margin-top: 12px;
        }
        .action-btn {
          flex: 1;
          padding: 10px 16px;
          border: none;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .action-btn.snooze {
          background: rgba(254,202,87,0.2);
          color: #feca57;
        }
        .action-btn.dismiss {
          background: rgba(78,205,196,0.2);
          color: #4ecdc4;
        }
        .action-btn.cancel {
          background: rgba(255,107,107,0.2);
          color: #ff6b6b;
        }
        .action-btn:hover {
          transform: translateY(-1px);
          filter: brightness(1.1);
        }
        .next-alarm {
          background: linear-gradient(135deg, rgba(255,217,61,0.1), rgba(255,217,61,0.05));
          border: 1px solid rgba(255,217,61,0.3);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
        }
        .next-alarm-label {
          font-size: 12px;
          color: #ffd93d;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 4px;
        }
        .next-alarm-time {
          font-size: 36px;
          font-weight: 700;
          color: #fff;
        }
        .next-alarm-info {
          display: flex;
          gap: 12px;
          margin-top: 8px;
          font-size: 14px;
          color: #a8a8a8;
        }
        .empty-state {
          text-align: center;
          padding: 32px 16px;
          color: #666;
        }
        .empty-state .icon {
          font-size: 48px;
          margin-bottom: 12px;
        }
      `;
      this.shadowRoot.appendChild(style);
    }

    const state = hass.states['sensor.sunrise_alarm_next'];
    const alarms = Object.keys(hass.states)
      .filter(k => k.startsWith('alarm.') && !k.includes('_'))
      .map(k => ({ id: k, ...hass.states[k] }));

    this.content.innerHTML = `
      <div class="card-header">
        <span class="card-title">🌅 Sonnenlicht-Wecker</span>
        <span class="card-icon">☀️</span>
      </div>
      ${state ? `
        <div class="next-alarm">
          <div class="next-alarm-label">Nächster Wecker</div>
          <div class="next-alarm-time">${state.state}</div>
          <div class="next-alarm-info">
            <span>👤 ${state.attributes.person_id || '—'}</span>
            <span>📍 ${state.attributes.zone_id || '—'}</span>
          </div>
        </div>
      ` : ''}
      <div class="alarm-list">
        ${alarms.length === 0 ? `
          <div class="empty-state">
            <div class="icon">⏰</div>
            <div>Keine Alarme konfiguriert</div>
          </div>
        ` : alarms.map(alarm => `
          <div class="alarm-item ${alarm.state}">
            <div class="alarm-header">
              <div>
                <div class="alarm-time">${alarm.attributes.time || '—'}</div>
                <div class="alarm-label">${alarm.attributes.label || alarm.attributes.name || 'Wecker'}</div>
              </div>
            </div>
            <div class="alarm-meta">
              ${alarm.attributes.zone_id ? `<span class="alarm-badge zone">📍 ${alarm.attributes.zone_id}</span>` : ''}
              ${alarm.attributes.person_id ? `<span class="alarm-badge person">👤 ${alarm.attributes.person_id}</span>` : ''}
              ${alarm.state === 'running' ? `<span class="alarm-badge">🔔 Läuft</span>` : ''}
              ${alarm.state === 'snoozed' ? `<span class="alarm-badge">💤 Gesnoozt</span>` : ''}
            </div>
            ${alarm.state === 'running' && alarm.attributes.progress_pct !== undefined ? `
              <div class="progress-bar">
                <div class="progress-fill" style="width: ${alarm.attributes.progress_pct}%"></div>
              </div>
            ` : ''}
            ${alarm.state === 'running' || alarm.state === 'snoozed' ? `
              <div class="alarm-actions">
                <button class="action-btn snooze" onclick="callService('sunrise_alarm.snooze', '${alarm.id}')">💤 Snooze</button>
                <button class="action-btn dismiss" onclick="callService('sunrise_alarm.dismiss', '${alarm.id}')">✓ OK</button>
              </div>
            ` : ''}
          </div>
        `).join('')}
      </div>
    `;
  }
}

customElements.define('sunrise-alarm-card', SunriseAlarmCard);
