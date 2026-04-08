/**
 * PilotSuite Lovelace Custom Cards v4.0.0
 *
 * Cards: ha-copilot-mood-card, ha-copilot-neurons-card, ha-copilot-habitus-card
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

console.info(
  "%c PilotSuite Cards v4.0.0 loaded ",
  "color: white; background: #4a90d9; font-weight: bold; padding: 2px 8px; border-radius: 4px;"
);
