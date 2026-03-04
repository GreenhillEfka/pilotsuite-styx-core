/**
 * PilotSuite Lovelace Custom Cards v5.0.0
 *
 * Cards: ha-copilot-mood-card, ha-copilot-neurons-card, ha-copilot-habitus-card,
 *        ha-copilot-styx-dashboard-card, ha-copilot-module-control-card,
 *        ha-copilot-habitus-zone-card
 *
 * These cards use Home Assistant's built-in LitElement (no external deps).
 * Load as a Lovelace resource: /api/v1/cards/pilotsuite-cards.js
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// ============================================================
// Mood Card
// ============================================================

class HaCopilotMoodCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
    };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Mood card requires an entity");
    this._config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.ai_home_copilot_mood" };
  }

  render() {
    if (!this.hass || !this._config) return html``;

    const stateObj = this.hass.states[this._config.entity];
    if (!stateObj) {
      return html`<ha-card header="${this._config.title || "Mood"}">
        <div class="content">Entity ${this._config.entity} not found</div>
      </ha-card>`;
    }

    const mood = stateObj.state;
    const confidence = stateObj.attributes.confidence;
    const emotions = this._parseEmotions(stateObj);
    const lastUpdated = stateObj.attributes.last_updated;

    return html`
      <ha-card header="${this._config.title || "Mood"}">
        <div class="content">
          <div class="mood-display">
            <div class="mood-icon">${this._getMoodEmoji(mood)}</div>
            <div class="mood-text">
              <span class="primary">${mood}</span>
              ${confidence != null
                ? html`<span class="confidence"
                    >(${(confidence * 100).toFixed(0)}%)</span
                  >`
                : ""}
            </div>
          </div>
          <div class="emotions">
            ${emotions.map(
              (e) => html`
                <div class="emotion-bar">
                  <span class="emotion-name">${e.name}</span>
                  <div class="emotion-progress">
                    <div
                      class="emotion-fill"
                      style="width:${e.value * 100}%"
                    ></div>
                  </div>
                  <span class="emotion-value"
                    >${(e.value * 100).toFixed(0)}%</span
                  >
                </div>
              `
            )}
          </div>
          ${lastUpdated
            ? html`<div class="timestamp">
                ${new Date(lastUpdated).toLocaleTimeString("de-DE", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>`
            : ""}
        </div>
      </ha-card>
    `;
  }

  _parseEmotions(stateObj) {
    const emotions = stateObj.attributes.emotions || [];
    const limit = this._config.show_emotions || 3;
    if (Array.isArray(emotions)) return emotions.slice(0, limit);
    if (typeof emotions === "object") {
      return Object.entries(emotions)
        .slice(0, limit)
        .map(([name, value]) => ({ name, value }));
    }
    return [];
  }

  _getMoodEmoji(mood) {
    const map = {
      happy: "\u{1F60A}",
      sad: "\u{1F622}",
      angry: "\u{1F620}",
      excited: "\u26A1",
      calm: "\u{1F33F}",
      neutral: "\u{1F610}",
      focused: "\u{1F3AF}",
      creative: "\u{1F3A8}",
      tired: "\u{1F634}",
      hungry: "\u{1F37D}\uFE0F",
    };
    return map[mood] || "\u{1F642}";
  }

  static get styles() {
    return css`
      .content { padding: 16px; }
      .mood-display { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
      .mood-icon { font-size: 48px; line-height: 1; }
      .primary { font-size: 24px; font-weight: bold; color: var(--primary-text-color); }
      .confidence { color: var(--secondary-text-color); font-size: 14px; margin-left: 8px; }
      .emotions { margin-top: 12px; }
      .emotion-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
      .emotion-name { width: 100px; font-size: 14px; color: var(--primary-text-color); }
      .emotion-progress { flex: 1; height: 8px; background: var(--divider-color); border-radius: 4px; overflow: hidden; }
      .emotion-fill { height: 100%; background: var(--primary-color); border-radius: 4px; transition: width .3s ease; }
      .emotion-value { width: 50px; text-align: right; font-size: 14px; color: var(--secondary-text-color); }
      .timestamp { margin-top: 16px; text-align: right; font-size: 12px; color: var(--secondary-text-color); }
    `;
  }
}

customElements.define("ha-copilot-mood-card", HaCopilotMoodCard);

// ============================================================
// Neurons Card
// ============================================================

class HaCopilotNeuronsCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
    };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Neurons card requires an entity");
    this._config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.ai_home_copilot_neuron_activity" };
  }

  render() {
    if (!this.hass || !this._config) return html``;

    const stateObj = this.hass.states[this._config.entity];
    if (!stateObj) {
      return html`<ha-card header="${this._config.title || "Neurons"}">
        <div class="content">Entity ${this._config.entity} not found</div>
      </ha-card>`;
    }

    const activity = stateObj.attributes.activity || [];
    const activeCount = activity.filter((n) => n.active).length;
    const totalCount = activity.length;
    const history = stateObj.attributes.history || [];
    const maxH = Math.max(...history.map((h) => h.value), 1);

    return html`
      <ha-card header="${this._config.title || "Neurons"}">
        <div class="content">
          <div class="status-row">
            <div class="status-item">
              <span class="label">Active</span>
              <span class="value active">${activeCount}</span>
            </div>
            <div class="status-item">
              <span class="label">Total</span>
              <span class="value">${totalCount}</span>
            </div>
            <div class="status-item">
              <span class="label">Activity</span>
              <span class="value">${stateObj.state}</span>
            </div>
          </div>
          <div class="activity-grid">
            ${activity.map(
              (n) => html`
                <div class="neuron-item ${n.active ? "active" : ""}">
                  <div class="neuron-icon">${n.active ? "\u26A1" : "\u2022"}</div>
                  <div class="neuron-info">
                    <div class="neuron-name">${n.name}</div>
                    <div class="neuron-status">
                      ${n.active ? "Active" : "Idle"}
                    </div>
                  </div>
                </div>
              `
            )}
          </div>
          ${history.length >= 2
            ? html`
                <div class="activity-chart">
                  <div class="chart-label">Activity History</div>
                  <div class="chart-bars">
                    ${history.map(
                      (h) => html`
                        <div
                          class="chart-bar"
                          style="height:${(h.value / maxH) * 100}%"
                        >
                          <div class="chart-tooltip">${h.value}</div>
                        </div>
                      `
                    )}
                  </div>
                </div>
              `
            : ""}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      .content { padding: 16px; }
      .status-row { display: flex; justify-content: space-around; margin-bottom: 24px; }
      .status-item { text-align: center; }
      .label { display: block; font-size: 12px; color: var(--secondary-text-color); margin-bottom: 4px; }
      .value { font-size: 20px; font-weight: bold; color: var(--primary-text-color); }
      .value.active { color: var(--success-color, #4caf50); }
      .activity-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin-bottom: 24px; }
      .neuron-item { display: flex; align-items: center; gap: 12px; padding: 8px; background: var(--card-background-color); border-radius: 8px; }
      .neuron-item.active { background: rgba(76,175,80,.1); border: 1px solid var(--success-color, #4caf50); }
      .neuron-icon { font-size: 16px; }
      .neuron-name { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .neuron-status { font-size: 12px; color: var(--secondary-text-color); }
      .activity-chart { margin-top: 20px; }
      .chart-label { font-size: 14px; color: var(--secondary-text-color); margin-bottom: 8px; }
      .chart-bars { display: flex; align-items: flex-end; gap: 4px; height: 60px; }
      .chart-bar { flex: 1; background: linear-gradient(180deg, var(--primary-color) 0%, rgba(100,100,100,.3) 100%); border-radius: 2px 2px 0 0; position: relative; transition: height .3s ease; }
      .chart-tooltip { position: absolute; top: -24px; left: 50%; transform: translateX(-50%); font-size: 12px; background: rgba(0,0,0,.8); color: white; padding: 4px 8px; border-radius: 4px; white-space: nowrap; opacity: 0; transition: opacity .3s ease; pointer-events: none; }
      .chart-bar:hover .chart-tooltip { opacity: 1; }
    `;
  }
}

customElements.define("ha-copilot-neurons-card", HaCopilotNeuronsCard);

// ============================================================
// Habitus Card
// ============================================================

class HaCopilotHabitusCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _selectedZone: { state: true },
    };
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Habitus card requires an entity");
    this._config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.ai_home_copilot_habitus_zones" };
  }

  render() {
    if (!this.hass || !this._config) return html``;

    const stateObj = this.hass.states[this._config.entity];
    if (!stateObj) {
      return html`<ha-card header="${this._config.title || "Habitus"}">
        <div class="content">Entity ${this._config.entity} not found</div>
      </ha-card>`;
    }

    const zones = stateObj.attributes.zones || [];
    const currentZone =
      zones.find((z) => z.id === this._selectedZone) ||
      zones.find((z) => z.active) ||
      zones[0];
    const behaviors = stateObj.attributes.behaviors || [];

    return html`
      <ha-card header="${this._config.title || "Habitus"}">
        <div class="content">
          <div class="zone-selector">
            ${zones.map(
              (z) => html`
                <button
                  class="zone-btn ${z.id === currentZone?.id ? "active" : ""}"
                  @click="${() => {
                    this._selectedZone = z.id;
                  }}"
                >
                  ${z.name}
                </button>
              `
            )}
          </div>
          ${currentZone
            ? html`
                <div class="zone-content">
                  <div class="zone-header">
                    <div class="zone-icon">\u{1F3E0}</div>
                    <div class="zone-info">
                      <div class="zone-name">${currentZone.name}</div>
                      <div class="zone-desc">
                        ${currentZone.description || ""}
                      </div>
                    </div>
                  </div>
                  ${currentZone.settings
                    ? html`
                        <div class="zone-settings">
                          <div class="s-item">
                            <span class="s-label">Ambience</span>
                            <span class="s-value"
                              >${currentZone.settings.ambience ||
                              "Normal"}</span
                            >
                          </div>
                          <div class="s-item">
                            <span class="s-label">Activity</span>
                            <span class="s-value"
                              >${currentZone.settings.activity ||
                              "Resting"}</span
                            >
                          </div>
                          <div class="s-item">
                            <span class="s-label">Optimization</span>
                            <span class="s-value"
                              >${currentZone.settings.optimization ||
                              "Balanced"}</span
                            >
                          </div>
                        </div>
                      `
                    : ""}
                  ${currentZone.mood
                    ? html`
                        <div class="zone-mood">
                          <div class="m-label">Current Mood</div>
                          <div class="m-bar">
                            <div
                              class="m-fill"
                              style="width:${currentZone.mood.intensity * 100}%"
                            ></div>
                          </div>
                          <div class="m-text">${currentZone.mood.type}</div>
                        </div>
                      `
                    : ""}
                </div>
              `
            : ""}
          ${behaviors.length > 0
            ? html`
                <div class="behaviors">
                  <div class="b-title">Recent Behaviors</div>
                  ${behaviors.slice(0, 5).map(
                    (b) => html`
                      <div class="b-item">
                        <div class="b-icon">${this._behaviorIcon(b.type)}</div>
                        <div class="b-info">
                          <div class="b-name">${b.name}</div>
                          <div class="b-time">
                            ${new Date(b.timestamp).toLocaleTimeString("de-DE", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </div>
                        </div>
                      </div>
                    `
                  )}
                </div>
              `
            : ""}
          ${currentZone
            ? html`
                <div class="homekit-section">
                  <div class="hk-title">
                    <span class="hk-icon"></span> HomeKit — ${currentZone.name} by Styx
                  </div>
                  <div class="hk-body">
                    <div class="hk-qr">
                      <img
                        src="${this._coreBase}/api/v1/homekit/qr/${currentZone.id}.svg"
                        alt="HomeKit QR"
                        class="hk-qr-img"
                        onerror="this.style.display='none'"
                      />
                    </div>
                    <div class="hk-info">
                      <div class="hk-detail">
                        <span class="hk-label">Apple Home</span>
                        <span class="hk-value">${currentZone.name} by Styx</span>
                      </div>
                      <div class="hk-detail">
                        <span class="hk-label">Entities</span>
                        <span class="hk-value">${currentZone.entity_count || 0}</span>
                      </div>
                      <div class="hk-hint">
                        Scanne den QR-Code mit der<br/>Apple Home App zum Pairen.
                      </div>
                    </div>
                  </div>
                </div>
              `
            : ""}
        </div>
      </ha-card>
    `;
  }

  get _coreBase() {
    // Try to get Core URL from entity attributes or default
    const stateObj = this.hass && this._config
      ? this.hass.states[this._config.entity]
      : null;
    if (stateObj && stateObj.attributes && stateObj.attributes.core_base) {
      return stateObj.attributes.core_base;
    }
    return "http://homeassistant.local:8909";
  }

  _behaviorIcon(type) {
    const map = {
      sleep: "\u{1F4A4}",
      work: "\u{1F4BB}",
      relax: "\u{1F6CB}\uFE0F",
      social: "\u{1F465}",
      creative: "\u{1F3A8}",
      exercise: "\u{1F3C3}",
      learning: "\u{1F4DA}",
      eating: "\u{1F37D}\uFE0F",
    };
    return map[type] || "\u23F0";
  }

  static get styles() {
    return css`
      .content { padding: 16px; }
      .zone-selector { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
      .zone-btn { padding: 8px 16px; background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 20px; cursor: pointer; font-size: 14px; color: var(--primary-text-color); transition: all .3s ease; }
      .zone-btn.active { background: var(--primary-color); color: white; border-color: var(--primary-color); }
      .zone-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
      .zone-icon { font-size: 32px; }
      .zone-name { font-size: 20px; font-weight: bold; color: var(--primary-text-color); }
      .zone-desc { font-size: 14px; color: var(--secondary-text-color); }
      .zone-settings { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; margin-bottom: 16px; }
      .s-item { display: flex; flex-direction: column; gap: 4px; }
      .s-label { font-size: 12px; color: var(--secondary-text-color); }
      .s-value { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .zone-mood { margin-top: 16px; }
      .m-label { font-size: 14px; color: var(--secondary-text-color); margin-bottom: 8px; }
      .m-bar { height: 8px; background: var(--divider-color); border-radius: 4px; overflow: hidden; margin-bottom: 8px; }
      .m-fill { height: 100%; background: linear-gradient(90deg, var(--primary-color), var(--accent-color, #ff9800)); border-radius: 4px; transition: width .3s ease; }
      .m-text { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .behaviors { margin-top: 24px; }
      .b-title { font-size: 14px; color: var(--secondary-text-color); margin-bottom: 12px; }
      .b-item { display: flex; align-items: center; gap: 12px; padding: 8px; background: var(--card-background-color); border-radius: 8px; margin-bottom: 8px; }
      .b-icon { font-size: 20px; }
      .b-name { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .b-time { font-size: 12px; color: var(--secondary-text-color); }

      /* HomeKit Section */
      .homekit-section {
        margin-top: 24px;
        padding: 16px;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 12px;
      }
      .hk-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--primary-text-color);
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .hk-icon { font-size: 18px; }
      .hk-body {
        display: flex;
        gap: 16px;
        align-items: flex-start;
      }
      .hk-qr {
        flex-shrink: 0;
        width: 120px;
        height: 120px;
        background: white;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      }
      .hk-qr-img {
        width: 112px;
        height: 112px;
        object-fit: contain;
      }
      .hk-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .hk-detail {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .hk-label {
        font-size: 12px;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .hk-value {
        font-size: 14px;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .hk-hint {
        margin-top: 4px;
        font-size: 12px;
        color: var(--secondary-text-color);
        line-height: 1.4;
        font-style: italic;
      }
    `;
  }
}

customElements.define("ha-copilot-habitus-card", HaCopilotHabitusCard);

// ============================================================
// Card Registration for HA Card Picker
// ============================================================

window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: "ha-copilot-mood-card",
    name: "PilotSuite Mood",
    description: "Displays current mood context with emotions breakdown",
    preview: true,
  },
  {
    type: "ha-copilot-neurons-card",
    name: "PilotSuite Neurons",
    description: "Shows neuron status, activity grid, and history chart",
    preview: true,
  },
  {
    type: "ha-copilot-habitus-card",
    name: "PilotSuite Habitus",
    description: "Habitus zones with settings, mood, and behavior history",
    preview: true,
  }
);

// ============================================================
// Styx Dashboard Card (compact overview)
// ============================================================

class HaCopilotStyxDashboardCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _data: { state: true },
    };
  }

  setConfig(config) {
    this._config = config;
    this._coreUrl = config.core_url || "/api/copilot_proxy";
  }

  static getStubConfig() {
    return { core_url: "/api/copilot_proxy" };
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._timer) {
      this._fetchData();
      this._timer = setInterval(() => this._fetchData(), 30000);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  }

  async _fetchData() {
    try {
      const headers = this.hass ? { Authorization: "Bearer " + this.hass.auth.accessToken } : {};
      const resp = await fetch(this._coreUrl + "/api/v1/styx/dashboard/compact", { headers });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      this._data = await resp.json();
    } catch (e) {
      this._data = { error: e.message };
    }
  }

  render() {
    if (!this._data) return html`<ha-card header="Styx Dashboard"><div class="content">Loading…</div></ha-card>`;
    if (this._data.error) return html`<ha-card header="Styx Dashboard"><div class="content error">${this._data.error}</div></ha-card>`;

    const mood = this._data.mood || {};
    const bus = this._data.bus || {};
    const modules = this._data.modules || {};
    const moodLabel = mood.dominant_mood || mood.mood || "—";
    const moodConf = mood.confidence != null ? (mood.confidence * 100).toFixed(0) + "%" : "";

    return html`
      <ha-card header="${this._config.title || "Styx Overview"}">
        <div class="content">
          <div class="stats-row">
            <div class="stat">
              <span class="stat-label">Mood</span>
              <span class="stat-value">${moodLabel}</span>
              ${moodConf ? html`<span class="stat-sub">${moodConf}</span>` : ""}
            </div>
            <div class="stat">
              <span class="stat-label">Bus Events</span>
              <span class="stat-value">${bus.events_published || 0}</span>
            </div>
            <div class="stat">
              <span class="stat-label">Errors</span>
              <span class="stat-value ${bus.errors > 0 ? "warn" : ""}">${bus.errors || 0}</span>
            </div>
          </div>
          <div class="modules-row">
            ${Object.entries(modules).map(([id, state]) => html`
              <span class="module-chip ${state}">${id.replace(/_/g, " ")}</span>
            `)}
          </div>
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      .content { padding: 16px; }
      .error { color: var(--error-color, #db4437); }
      .stats-row { display: flex; justify-content: space-around; margin-bottom: 16px; }
      .stat { text-align: center; }
      .stat-label { display: block; font-size: 12px; color: var(--secondary-text-color); margin-bottom: 4px; }
      .stat-value { font-size: 20px; font-weight: bold; color: var(--primary-text-color); }
      .stat-value.warn { color: var(--error-color, #db4437); }
      .stat-sub { display: block; font-size: 11px; color: var(--secondary-text-color); }
      .modules-row { display: flex; flex-wrap: wrap; gap: 6px; }
      .module-chip { padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; text-transform: capitalize; }
      .module-chip.active { background: rgba(76,175,80,.15); color: var(--success-color, #4caf50); }
      .module-chip.learning { background: rgba(255,152,0,.15); color: #ff9800; }
      .module-chip.off { background: rgba(244,67,54,.15); color: #f44336; }
    `;
  }
}

customElements.define("ha-copilot-styx-dashboard-card", HaCopilotStyxDashboardCard);

// ============================================================
// Module Control Card (interactive state toggle)
// ============================================================

class HaCopilotModuleControlCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _modules: { state: true },
    };
  }

  setConfig(config) {
    this._config = config;
    this._coreUrl = config.core_url || "/api/copilot_proxy";
  }

  static getStubConfig() {
    return { core_url: "/api/copilot_proxy" };
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._fetched) {
      this._fetched = true;
      this._fetchModules();
    }
  }

  async _fetchModules() {
    try {
      const headers = this.hass ? { Authorization: "Bearer " + this.hass.auth.accessToken } : {};
      const resp = await fetch(this._coreUrl + "/api/v1/styx/config", { headers });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      this._modules = data.modules || [];
    } catch (e) {
      this._modules = null;
    }
  }

  async _toggle(moduleId, currentState) {
    const states = ["active", "learning", "off"];
    const next = states[(states.indexOf(currentState) + 1) % states.length];
    try {
      const headers = {
        "Content-Type": "application/json",
        ...(this.hass ? { Authorization: "Bearer " + this.hass.auth.accessToken } : {}),
      };
      await fetch(this._coreUrl + `/api/v1/modules/${moduleId}/configure`, {
        method: "POST", headers, body: JSON.stringify({ state: next }),
      });
      this._fetchModules();
    } catch (e) { /* ignore */ }
  }

  render() {
    if (!this._modules) return html`<ha-card header="Module Control"><div class="content">Loading…</div></ha-card>`;

    const stateLabels = { active: "Active", learning: "Learning", off: "Off" };

    return html`
      <ha-card header="${this._config.title || "Module Control"}">
        <div class="content">
          ${this._modules.map(m => html`
            <div class="mod-row">
              <span class="mod-icon">${this._icon(m.icon)}</span>
              <div class="mod-info">
                <div class="mod-name">${m.label}</div>
                <div class="mod-desc">${m.description || ""}</div>
              </div>
              <button class="state-btn ${m.state}" @click="${() => this._toggle(m.id, m.state)}">
                ${stateLabels[m.state] || m.state}
              </button>
            </div>
          `)}
        </div>
      </ha-card>
    `;
  }

  _icon(mdi) {
    const map = {
      "mdi:emoticon": "\u{1F3AD}", "mdi:pickaxe": "\u26CF\uFE0F", "mdi:brain": "\u{1F9E0}",
      "mdi:chart-timeline-variant-shimmer": "\u{1F4CA}", "mdi:swap-horizontal": "\u{1F504}",
      "mdi:school": "\u{1F393}", "mdi:lightbulb-on": "\u{1F4A1}", "mdi:solar-power": "\u2600\uFE0F",
      "mdi:microphone": "\u{1F3A4}", "mdi:alert-circle": "\u26A0\uFE0F",
    };
    return map[mdi] || "\u2699\uFE0F";
  }

  static get styles() {
    return css`
      .content { padding: 16px; }
      .mod-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
      .mod-row:last-child { border-bottom: none; }
      .mod-icon { font-size: 18px; width: 28px; text-align: center; }
      .mod-info { flex: 1; min-width: 0; }
      .mod-name { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .mod-desc { font-size: 12px; color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .state-btn { border: none; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; cursor: pointer; min-width: 70px; text-align: center; transition: all .2s; }
      .state-btn:hover { filter: brightness(1.2); }
      .state-btn.active { background: rgba(76,175,80,.2); color: var(--success-color, #4caf50); }
      .state-btn.learning { background: rgba(255,152,0,.2); color: #ff9800; }
      .state-btn.off { background: rgba(244,67,54,.2); color: #f44336; }
    `;
  }
}

customElements.define("ha-copilot-module-control-card", HaCopilotModuleControlCard);

// ============================================================
// Habitus Zone Card (zone configuration display)
// ============================================================

class HaCopilotHabitusZoneCard extends LitElement {
  static get properties() {
    return {
      hass: { attribute: false },
      _config: { state: true },
      _zones: { state: true },
    };
  }

  setConfig(config) {
    this._config = config;
    this._coreUrl = config.core_url || "/api/copilot_proxy";
  }

  static getStubConfig() {
    return { core_url: "/api/copilot_proxy" };
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._fetched) {
      this._fetched = true;
      this._fetchZones();
    }
  }

  async _fetchZones() {
    try {
      const headers = this.hass ? { Authorization: "Bearer " + this.hass.auth.accessToken } : {};
      const resp = await fetch(this._coreUrl + "/api/v1/habitus/zones", { headers });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      this._zones = data.zones || data || [];
    } catch (e) {
      this._zones = null;
    }
  }

  render() {
    if (!this._zones) return html`<ha-card header="Habitus Zones"><div class="content">Loading…</div></ha-card>`;

    const zoneIcons = {
      living: "\u{1F6CB}\uFE0F", bedroom: "\u{1F6CF}\uFE0F", kitchen: "\u{1F373}",
      bath: "\u{1F6C1}", office: "\u{1F4BB}", garden: "\u{1F33F}",
      garage: "\u{1F697}", hallway: "\u{1F6AA}", kids: "\u{1F9F8}",
    };

    return html`
      <ha-card header="${this._config.title || "Habitus Zones"}">
        <div class="content">
          ${Array.isArray(this._zones) && this._zones.length > 0
            ? this._zones.map(z => html`
              <div class="zone-row">
                <span class="zone-icon">${zoneIcons[z.zone_type || z.id] || "\u{1F3E0}"}</span>
                <div class="zone-info">
                  <div class="zone-name">${z.name_de || z.name || z.id}</div>
                  <div class="zone-meta">Priority: ${z.priority || "—"}</div>
                </div>
                ${z.metrics ? html`
                  <div class="zone-metrics">
                    <span class="metric">${z.metrics.entity_count || 0} entities</span>
                  </div>
                ` : ""}
              </div>
            `)
            : html`<div class="empty">No zones configured</div>`
          }
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      .content { padding: 16px; }
      .zone-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
      .zone-row:last-child { border-bottom: none; }
      .zone-icon { font-size: 22px; width: 32px; text-align: center; }
      .zone-info { flex: 1; }
      .zone-name { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
      .zone-meta { font-size: 12px; color: var(--secondary-text-color); }
      .zone-metrics { font-size: 12px; color: var(--secondary-text-color); }
      .metric { background: var(--card-background-color); padding: 2px 8px; border-radius: 8px; }
      .empty { text-align: center; padding: 20px; color: var(--secondary-text-color); font-size: 14px; }
    `;
  }
}

customElements.define("ha-copilot-habitus-zone-card", HaCopilotHabitusZoneCard);

// ============================================================
// Card Registration for HA Card Picker
// ============================================================

window.customCards.push(
  {
    type: "ha-copilot-styx-dashboard-card",
    name: "PilotSuite Styx Dashboard",
    description: "Compact overview: mood, bus stats, and module states",
    preview: true,
  },
  {
    type: "ha-copilot-module-control-card",
    name: "PilotSuite Module Control",
    description: "Interactive module state toggle (active/learning/off)",
    preview: true,
  },
  {
    type: "ha-copilot-habitus-zone-card",
    name: "PilotSuite Habitus Zones",
    description: "Displays habitus zone configuration and metrics",
    preview: true,
  }
);

console.info(
  "%c PilotSuite Cards v5.0.0 loaded ",
  "color: white; background: #4a90d9; font-weight: bold; padding: 2px 8px; border-radius: 4px;"
);
