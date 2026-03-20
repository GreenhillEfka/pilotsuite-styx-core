/**
 * Zone Editor Component
 * 
 * Lit-based zone management interface for PilotSuite
 * Features: Zone list, Create/Edit/Delete, Entity Drag&Drop, Auto-Save,
 * Validation, Loading States (Skeleton), Error Handling
 * 
 * API Endpoints:
 * - GET    /api/v1/zone-editor/zones
 * - POST   /api/v1/zone-editor/zones
 * - GET    /api/v1/zone-editor/zones/{id}
 * - PUT    /api/v1/zone-editor/zones/{id}
 * - DELETE /api/v1/zone-editor/zones/{id}
 * - POST   /api/v1/zone-editor/zones/{id}/rooms
 * - GET    /api/v1/zone-editor/rooms  (für verfügbare Räume)
 * 
 * @author Clawdya
 * @version 1.0.0
 */

import { LitElement, html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { classMap } from 'lit/directives/class-map.js';
import { zoneEditorStyles } from './zone_editor.styles.js';

// ============================================================================
// Type Definitions
// ============================================================================

export interface ZoneEntity {
  entity_id: string;
  name: string;
  domain?: string;
  state?: string;
  entity_count?: number;
}

export interface Zone {
  zone_id: string;
  name: string;
  floor?: number;
  area_sqm?: number;
  rooms?: ZoneEntity[];
  entities: ZoneEntity[];
  icon?: string;
  mode?: string;
  enabled?: boolean;
  priority?: number;
  status?: string;
  person_count?: number;
  room_count?: number;
  entity_count?: number;
}

export interface ZoneApiResponse {
  ok?: boolean;
  success?: boolean;
  data?: Zone[] | Zone;
  zones?: Zone[];
  zone?: Zone;
  error?: string;
  message?: string;
  total?: number;
}

export interface DragItem {
  entity_id: string;
  name: string;
  domain: string;
}

// ============================================================================
// Zone Editor Component
// ============================================================================

@customElement('zone-editor')
export class ZoneEditor extends LitElement {
  // API Configuration
  @property({ type: String })
  apiBaseUrl = '/api/v1/zone-editor';

  @property({ type: String })
  authToken = '';

  // State
  @state()
  private zones: Zone[] = [];

  @state()
  private selectedZone: Zone | null = null;

  @state()
  private isLoading = false;

  @state()
  private isSaving = false;

  @state()
  private error: string | null = null;

  @state()
  private successMessage: string | null = null;

  @state()
  private showCreateForm = false;

  @state()
  private editMode = false;

  @state()
  private draggedEntity: DragItem | null = null;

  @state()
  private availableEntities: ZoneEntity[] = [];

  // Form state
  @state()
  private formData = {
    zone_id: '',
    name: '',
    floor: 1,
    area_sqm: 0,
    icon: 'mdi:room',
    entities: [] as ZoneEntity[],
  };

  // Validation
  @state()
  private validationErrors: Record<string, string> = {};

  static override styles = zoneEditorStyles;

  // ============================================================================
  // Lifecycle
  // ============================================================================

  override firstUpdated() {
    this.loadZones();
    this.loadAvailableEntities();
  }

  // ============================================================================
  // Data Loading
  // ============================================================================

  async loadZones(): Promise<void> {
    this.isLoading = true;
    this.error = null;

    try {
      const response = await fetch(`${this.apiBaseUrl}/zones`, {
        method: 'GET',
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to load zones: ${response.status}`);
      }

      const result: ZoneApiResponse = await response.json();
      
      if (this.isApiSuccess(result)) {
        this.zones = this.normalizeZones(result);
      } else if (result.error) {
        throw new Error(result.error);
      } else {
        throw new Error('Malformed zone list response');
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load zones';
      console.error('Zone load error:', err);
    } finally {
      this.isLoading = false;
    }
  }

  async loadZoneDetails(zoneId: string): Promise<void> {
    this.isLoading = true;
    this.error = null;

    try {
      const response = await fetch(`${this.apiBaseUrl}/zones/${zoneId}`, {
        method: 'GET',
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to load zone: ${response.status}`);
      }

      const result: ZoneApiResponse = await response.json();

      const normalizedZone = this.normalizeZoneResponse(result);
      if (normalizedZone) {
        this.selectedZone = normalizedZone;
        this.editMode = false;
      } else {
        throw new Error(result.error || 'Malformed zone response');
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load zone details';
      console.error('Zone details load error:', err);
    } finally {
      this.isLoading = false;
    }
  }

  async loadAvailableEntities(): Promise<void> {
    try {
      const response = await fetch(`${this.apiBaseUrl}/rooms`, {
        method: 'GET',
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to load rooms: ${response.status}`);
      }

      const result: ZoneApiResponse & { rooms?: any[] } = await response.json();

      if (this.isApiSuccess(result)) {
        const roomList = Array.isArray(result.rooms) ? result.rooms : [];
        const normalized = roomList
          .filter(room => room)
          .map(room => this.normalizeRoomEntity(room));
        this.availableEntities = normalized.length > 0
          ? normalized
          : [
              { entity_id: 'kueche', name: 'Kitchen', domain: 'room' },
              { entity_id: 'wohnzimmer', name: 'Living Room', domain: 'room' },
            ];
        return;
      }

      throw new Error(result.error || 'Malformed room list response');
    } catch (err) {
      console.warn('Using fallback rooms:', err);
      this.availableEntities = [
        { entity_id: 'light.living_room_main', name: 'Living Room Light', domain: 'light' },
        { entity_id: 'light.kitchen_main', name: 'Kitchen Light', domain: 'light' },
        { entity_id: 'climate.living_room', name: 'Living Room Thermostat', domain: 'climate' },
        { entity_id: 'sensor.living_room_temp', name: 'Living Room Temperature', domain: 'sensor' },
        { entity_id: 'binary_sensor.motion_living', name: 'Motion Sensor', domain: 'binary_sensor' },
        { entity_id: 'media_player.living_room', name: 'Living Room TV', domain: 'media_player' },
        { entity_id: 'switch.coffee_machine', name: 'Coffee Machine', domain: 'switch' },
      ];
    }
  }

  // ============================================================================
  // CRUD Operations
  // ============================================================================

  async createZone(): Promise<void> {
    if (!this.validateForm()) {
      return;
    }

    this.isSaving = true;
    this.error = null;

    try {
      const payload = {
        ...this.formData,
        rooms: this.formData.entities.map(entity => entity.entity_id),
      };
      delete (payload as any).entities;

      const response = await fetch(`${this.apiBaseUrl}/zones`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to create zone: ${response.status}`);
      }

      const result: ZoneApiResponse = await response.json();
      
      if (this.isApiSuccess(result)) {
        this.successMessage = 'Zone created successfully';
        this.showCreateForm = false;
        this.resetForm();
        await this.loadZones();
        this.clearSuccessMessage();
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to create zone';
      console.error('Zone create error:', err);
    } finally {
      this.isSaving = false;
    }
  }

  async updateZone(): Promise<void> {
    if (!this.selectedZone || !this.validateForm()) {
      return;
    }

    this.isSaving = true;
    this.error = null;

    try {
      const payload = {
        ...this.formData,
        rooms: this.formData.entities.map(entity => entity.entity_id),
      };
      delete (payload as any).entities;

      const response = await fetch(`${this.apiBaseUrl}/zones/${this.selectedZone.zone_id}`, {
        method: 'PUT',
        headers: this.getHeaders(),
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to update zone: ${response.status}`);
      }

      const result: ZoneApiResponse = await response.json();

      if (this.isApiSuccess(result)) {
        this.successMessage = 'Zone updated successfully';
        this.editMode = false;
        await this.loadZones();
        await this.loadZoneDetails(this.selectedZone.zone_id);
        this.clearSuccessMessage();
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to update zone';
      console.error('Zone update error:', err);
    } finally {
      this.isSaving = false;
    }
  }

  async deleteZone(zoneId: string): Promise<void> {
    if (!confirm('Are you sure you want to delete this zone?')) {
      return;
    }

    this.isSaving = true;
    this.error = null;

    try {
      const response = await fetch(`${this.apiBaseUrl}/zones/${zoneId}`, {
        method: 'DELETE',
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        throw new Error(`Failed to delete zone: ${response.status}`);
      }

      const result: ZoneApiResponse = await response.json();
      
      if (this.isApiSuccess(result)) {
        this.successMessage = 'Zone deleted successfully';
        this.selectedZone = null;
        await this.loadZones();
        this.clearSuccessMessage();
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to delete zone';
      console.error('Zone delete error:', err);
    } finally {
      this.isSaving = false;
    }
  }

  async addEntityToZone(zoneId: string, entity: ZoneEntity): Promise<void> {
    this.isSaving = true;
    this.error = null;

    try {
      const response = await fetch(`${this.apiBaseUrl}/zones/${zoneId}/rooms`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({ room_id: entity.entity_id }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to add room: ${response.status}`);
      }

      const result: ZoneApiResponse = await response.json();
      
      if (this.isApiSuccess(result)) {
        this.successMessage = 'Room added successfully';
        await this.loadZoneDetails(zoneId);
        this.clearSuccessMessage();
      }
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to add room';
      console.error('Add room error:', err);
    } finally {
      this.isSaving = false;
    }
  }

  private normalizeRoomEntity(rawEntity: any): ZoneEntity {
    if (typeof rawEntity === 'string') {
      return {
        entity_id: rawEntity,
        name: rawEntity,
        domain: 'room',
      };
    }

    return {
      entity_id: String((rawEntity && (rawEntity.entity_id || rawEntity.room_id)) || ''),
      name: String((rawEntity && (rawEntity.name || rawEntity.zone_name || rawEntity.room_id)) || ''),
      domain: String(rawEntity?.domain || 'room'),
      entity_count: rawEntity?.entity_count,
      state: rawEntity?.state,
    };
  }

  private normalizeZone(rawZone: any): Zone {
    const rooms = Array.isArray(rawZone?.rooms)
      ? rawZone.rooms.map((room: any) => this.normalizeRoomEntity(room))
      : [];

    return {
      zone_id: String(rawZone?.zone_id || ''),
      name: String(rawZone?.name || ''),
      floor: rawZone?.floor,
      area_sqm: rawZone?.area_sqm,
      rooms,
      entities: rooms,
      icon: rawZone?.icon,
      mode: rawZone?.mode,
      enabled: rawZone?.enabled,
      priority: rawZone?.priority,
      status: rawZone?.status,
      person_count: rawZone?.person_count,
      room_count: rawZone?.room_count,
      entity_count: rawZone?.entity_count,
    };
  }

  private normalizeZones(result: ZoneApiResponse): Zone[] {
    const rawZones = Array.isArray(result.zones)
      ? result.zones
      : Array.isArray(result.data)
        ? (result.data as Zone[])
        : [];

    return rawZones
      .filter(zone => zone)
      .map((zone: any) => this.normalizeZone(zone));
  }

  private normalizeZoneResponse(result: ZoneApiResponse): Zone | null {
    if (!this.isApiSuccess(result)) {
      return null;
    }

    if ((result as any).zone) {
      return this.normalizeZone((result as any).zone);
    }

    if (result.data && !Array.isArray(result.data)) {
      return this.normalizeZone(result.data);
    }

    return null;
  }

  private isApiSuccess(result: ZoneApiResponse): boolean {
    return Boolean(result && (result.ok || result.success));
  }

  // ============================================================================
  // Drag & Drop
  // ============================================================================

  handleDragStart(e: DragEvent, entity: ZoneEntity): void {
    this.draggedEntity = {
      entity_id: entity.entity_id,
      name: entity.name,
      domain: entity.domain,
    };
    e.dataTransfer?.setData('text/plain', JSON.stringify(this.draggedEntity));
    e.dataTransfer!.effectAllowed = 'copy';
  }

  handleDragOver(e: DragEvent): void {
    e.preventDefault();
    e.dataTransfer!.dropEffect = 'copy';
  }

  handleDrop(e: DragEvent): void {
    e.preventDefault();
    
    if (!this.selectedZone) return;

    try {
      const data = e.dataTransfer?.getData('text/plain');
      if (data) {
        const entity: DragItem = JSON.parse(data);
        
        // Check if entity already exists in zone
        const exists = this.formData.entities.some(
          e => e.entity_id === entity.entity_id
        );

        if (!exists) {
          this.formData.entities.push({
            entity_id: entity.entity_id,
            name: entity.name,
            domain: entity.domain,
          });
          this.validateForm();
        }
      }
    } catch (err) {
      console.error('Drop error:', err);
    }
  }

  removeEntity(entityId: string): void {
    this.formData.entities = this.formData.entities.filter(
      e => e.entity_id !== entityId
    );
    this.validateForm();
  }

  // ============================================================================
  // Form Handling
  // ============================================================================

  startCreateMode(): void {
    this.resetForm();
    this.showCreateForm = true;
    this.editMode = false;
    this.selectedZone = null;
    this.validationErrors = {};
  }

  startEditMode(): void {
    if (!this.selectedZone) return;

    this.formData = {
      zone_id: this.selectedZone.zone_id,
      name: this.selectedZone.name,
      floor: this.selectedZone.floor || 1,
      area_sqm: this.selectedZone.area_sqm || 0,
      icon: this.selectedZone.icon || 'mdi:room',
      entities: this.selectedZone.entities || [],
    };
    this.editMode = true;
    this.validationErrors = {};
  }

  cancelEdit(): void {
    this.editMode = false;
    if (this.selectedZone) {
      this.formData = {
        zone_id: this.selectedZone.zone_id,
        name: this.selectedZone.name,
        floor: this.selectedZone.floor || 1,
        area_sqm: this.selectedZone.area_sqm || 0,
        icon: this.selectedZone.icon || 'mdi:room',
        entities: this.selectedZone.entities || [],
      };
    }
    this.validationErrors = {};
  }

  resetForm(): void {
    this.formData = {
      zone_id: '',
      name: '',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [],
    };
    this.validationErrors = {};
  }

  validateForm(): boolean {
    this.validationErrors = {};

    // Name is required
    if (!this.formData.name.trim()) {
      this.validationErrors.name = 'Name is required';
    }

    // Zone ID is required for creation
    if (!this.formData.zone_id.trim() && !this.selectedZone) {
      this.validationErrors.zone_id = 'Zone ID is required';
    }

    // At least 1 room required
    if (this.formData.entities.length === 0) {
      this.validationErrors.entities = 'At least one room is required';
    }

    return Object.keys(this.validationErrors).length === 0;
  }

  handleFormInput(field: string, value: string | number): void {
    this.formData = {
      ...this.formData,
      [field]: value,
    };
    
    // Clear validation error for this field
    if (this.validationErrors[field]) {
      this.validationErrors = { ...this.validationErrors };
      delete this.validationErrors[field];
    }
  }

  // ============================================================================
  // Auto-Save (debounced)
  // ============================================================================

  private autoSaveTimeout: number | null = null;

  triggerAutoSave(): void {
    if (this.autoSaveTimeout) {
      clearTimeout(this.autoSaveTimeout);
    }

    this.autoSaveTimeout = window.setTimeout(() => {
      if (this.editMode && this.selectedZone) {
        this.updateZone();
      }
    }, 1000); // 1 second debounce
  }

  // ============================================================================
  // Utilities
  // ============================================================================

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    return headers;
  }

  private clearSuccessMessage(): void {
    setTimeout(() => {
      this.successMessage = null;
    }, 3000);
  }

  // ============================================================================
  // Render
  // ============================================================================

  override render() {
    return html`
      <div class="zone-editor-container">
        <!-- Header -->
        <div class="header">
          <h2>🏠 Zone Editor</h2>
          <button 
            class="btn btn-primary" 
            @click=${this.startCreateMode}
            ?disabled=${this.showCreateForm}
          >
            + New Zone
          </button>
        </div>

        <!-- Success/Error Messages -->
        ${this.successMessage 
          ? html`<div class="message success">✓ ${this.successMessage}</div>` 
          : nothing
        }
        
        ${this.error 
          ? html`<div class="message error">⚠️ ${this.error}</div>` 
          : nothing
        }

        <!-- Main Content -->
        <div class="main-content">
          <!-- Zone List -->
          <div class="zone-list-panel">
            <h3>Zones</h3>
            
            ${this.isLoading && this.zones.length === 0
              ? this.renderSkeletonList()
              : html`
                  <div class="zone-list">
                    ${this.zones.map(zone => this.renderZoneListItem(zone))}
                  </div>
                `
            }
          </div>

          <!-- Zone Detail / Form -->
          <div class="zone-detail-panel">
            ${this.showCreateForm
              ? this.renderCreateForm()
              : this.selectedZone
                ? this.editMode
                  ? this.renderEditForm()
                  : this.renderZoneDetail()
                : html`
                    <div class="empty-state">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <path d="M9 3v18"/>
                        <path d="M15 3v18"/>
                        <path d="M3 9h18"/>
                        <path d="M3 15h18"/>
                      </svg>
                      <h3>Select a Zone</h3>
                      <p>Choose a zone from the list or create a new one</p>
                    </div>
                  `
            }
          </div>
        </div>

        <!-- Available Rooms (for drag & drop) -->
        ${this.editMode || this.showCreateForm
          ? html`
              <div class="available-entities-panel">
                <h3>Available Rooms</h3>
                <p class="hint">Drag rooms to the zone</p>
                <div class="entity-list">
                  ${this.availableEntities.map(entity => 
                    this.renderDraggableEntity(entity)
                  )}
                </div>
              </div>
            `
          : nothing
        }
      </div>
    `;
  }

  private renderSkeletonList() {
    return html`
      <div class="skeleton-list">
        ${Array(5).fill(null).map(() => html`
          <div class="skeleton-item">
            <div class="skeleton-line short"></div>
            <div class="skeleton-line"></div>
          </div>
        `)}
      </div>
    `;
  }

  private renderZoneListItem(zone: Zone) {
    const isSelected = this.selectedZone?.zone_id === zone.zone_id;
    
    return html`
      <div 
        class=${classMap({ 
          'zone-list-item': true, 
          selected: isSelected,
        })}
        @click=${() => this.loadZoneDetails(zone.zone_id)}
      >
        <div class="zone-icon">
          ${zone.icon ? html`<span>${zone.icon}</span>` : html`🏠`}
        </div>
        <div class="zone-info">
          <div class="zone-name">${zone.name}</div>
          <div class="zone-meta">
            ${zone.entities?.length || 0} rooms
            ${zone.floor ? html` • Floor ${zone.floor}` : nothing}
          </div>
        </div>
      </div>
    `;
  }

  private renderZoneDetail() {
    if (!this.selectedZone) return nothing;

    return html`
      <div class="zone-detail">
        <div class="detail-header">
          <h3>${this.selectedZone.name}</h3>
          <div class="detail-actions">
            <button 
              class="btn btn-secondary" 
              @click=${this.startEditMode}
            >
              Edit
            </button>
            <button 
              class="btn btn-danger" 
              @click=${() => this.deleteZone(this.selectedZone!.zone_id)}
              ?disabled=${this.isSaving}
            >
              Delete
            </button>
          </div>
        </div>

        <div class="detail-info">
          <div class="info-row">
            <span class="label">Zone ID:</span>
            <span class="value">${this.selectedZone.zone_id}</span>
          </div>
          ${this.selectedZone.floor
            ? html`
                <div class="info-row">
                  <span class="label">Floor:</span>
                  <span class="value">${this.selectedZone.floor}</span>
                </div>
              `
            : nothing
          }
          ${this.selectedZone.area_sqm
            ? html`
                <div class="info-row">
                  <span class="label">Area:</span>
                  <span class="value">${this.selectedZone.area_sqm} m²</span>
                </div>
              `
            : nothing
          }
        </div>

        <div class="entities-section">
          <h4>Rooms (${this.selectedZone.entities?.length || 0})</h4>
          ${this.selectedZone.entities && this.selectedZone.entities.length > 0
            ? html`
                <div class="entity-list">
                  ${this.selectedZone.entities.map(entity => 
                    html`
                      <div class="entity-item">
                        <span class="entity-domain">${entity.domain}</span>
                        <span class="entity-name">${entity.name}</span>
                        <span class="entity-id">${entity.entity_id}</span>
                      </div>
                    `
                  )}
                </div>
              `
            : html`<p class="no-entities">No rooms in this zone</p>`
          }
        </div>
      </div>
    `;
  }

  private renderCreateForm() {
    return html`
      <div class="form-container">
        <div class="form-header">
          <h3>Create New Zone</h3>
          <button class="btn btn-icon" @click=${() => this.showCreateForm = false}>✕</button>
        </div>

        <form @submit=${(e: Event) => { e.preventDefault(); this.createZone(); }}>
          <div class="form-group">
            <label for="zone_id">Zone ID</label>
            <input
              id="zone_id"
              type="text"
              .value=${this.formData.zone_id}
              @input=${(e: Event) => this.handleFormInput('zone_id', (e.target as HTMLInputElement).value)}
              ?disabled=${this.isSaving}
              placeholder="e.g., zone:living_room"
            />
            ${this.validationErrors.zone_id
              ? html`<div class="error-text">${this.validationErrors.zone_id}</div>`
              : nothing
            }
          </div>

          <div class="form-group">
            <label for="name">Name *</label>
            <input
              id="name"
              type="text"
              .value=${this.formData.name}
              @input=${(e: Event) => this.handleFormInput('name', (e.target as HTMLInputElement).value)}
              ?disabled=${this.isSaving}
              placeholder="e.g., Living Room"
              required
            />
            ${this.validationErrors.name
              ? html`<div class="error-text">${this.validationErrors.name}</div>`
              : nothing
            }
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="floor">Floor</label>
              <input
                id="floor"
                type="number"
                .value=${this.formData.floor}
                @input=${(e: Event) => this.handleFormInput('floor', parseInt((e.target as HTMLInputElement).value))}
                ?disabled=${this.isSaving}
                min="0"
              />
            </div>

            <div class="form-group">
              <label for="area_sqm">Area (m²)</label>
              <input
                id="area_sqm"
                type="number"
                .value=${this.formData.area_sqm}
                @input=${(e: Event) => this.handleFormInput('area_sqm', parseFloat((e.target as HTMLInputElement).value))}
                ?disabled=${this.isSaving}
                min="0"
                step="0.1"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="icon">Icon</label>
            <input
              id="icon"
              type="text"
              .value=${this.formData.icon}
              @input=${(e: Event) => this.handleFormInput('icon', (e.target as HTMLInputElement).value)}
              ?disabled=${this.isSaving}
              placeholder="mdi:room"
            />
          </div>

          <div class="form-group">
            <label>Rooms *</label>
            <div 
              class="entity-drop-zone"
              @dragover=${this.handleDragOver}
              @drop=${this.handleDrop}
            >
              ${this.formData.entities.length === 0
                ? html`<div class="drop-placeholder">Drag rooms here</div>`
                : html`
                    <div class="entity-list">
                      ${this.formData.entities.map(entity => 
                        html`
                          <div class="entity-item removable">
                            <span class="entity-domain">${entity.domain}</span>
                            <span class="entity-name">${entity.name}</span>
                            <button 
                              type="button"
                              class="btn-remove"
                              @click=${() => this.removeEntity(entity.entity_id)}
                            >
                              ✕
                            </button>
                          </div>
                        `
                      )}
                    </div>
                  `
              }
            </div>
            ${this.validationErrors.entities
              ? html`<div class="error-text">${this.validationErrors.entities}</div>`
              : nothing
            }
          </div>

          <div class="form-actions">
            <button 
              type="button"
              class="btn btn-secondary" 
              @click=${() => this.showCreateForm = false}
              ?disabled=${this.isSaving}
            >
              Cancel
            </button>
            <button 
              type="submit"
              class="btn btn-primary"
              ?disabled=${this.isSaving || !this.formData.name.trim() || this.formData.entities.length === 0}
            >
              ${this.isSaving ? html`<div class="spinner"></div>` : nothing}
              Create Zone
            </button>
          </div>
        </form>
      </div>
    `;
  }

  private renderEditForm() {
    return html`
      <div class="form-container">
        <div class="form-header">
          <h3>Edit Zone</h3>
          <button class="btn btn-icon" @click=${this.cancelEdit}>✕</button>
        </div>

        <form @submit=${(e: Event) => { e.preventDefault(); this.updateZone(); }}>
          <div class="form-group">
            <label for="edit_zone_id">Zone ID</label>
            <input
              id="edit_zone_id"
              type="text"
              .value=${this.formData.zone_id}
              disabled
              class="disabled-input"
            />
          </div>

          <div class="form-group">
            <label for="edit_name">Name *</label>
            <input
              id="edit_name"
              type="text"
              .value=${this.formData.name}
              @input=${(e: Event) => this.handleFormInput('name', (e.target as HTMLInputElement).value)}
              @change=${this.triggerAutoSave}
              ?disabled=${this.isSaving}
              required
            />
            ${this.validationErrors.name
              ? html`<div class="error-text">${this.validationErrors.name}</div>`
              : nothing
            }
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="edit_floor">Floor</label>
              <input
                id="edit_floor"
                type="number"
                .value=${this.formData.floor}
                @input=${(e: Event) => this.handleFormInput('floor', parseInt((e.target as HTMLInputElement).value))}
                @change=${this.triggerAutoSave}
                ?disabled=${this.isSaving}
                min="0"
              />
            </div>

            <div class="form-group">
              <label for="edit_area_sqm">Area (m²)</label>
              <input
                id="edit_area_sqm"
                type="number"
                .value=${this.formData.area_sqm}
                @input=${(e: Event) => this.handleFormInput('area_sqm', parseFloat((e.target as HTMLInputElement).value))}
                @change=${this.triggerAutoSave}
                ?disabled=${this.isSaving}
                min="0"
                step="0.1"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="edit_icon">Icon</label>
            <input
              id="edit_icon"
              type="text"
              .value=${this.formData.icon}
              @input=${(e: Event) => this.handleFormInput('icon', (e.target as HTMLInputElement).value)}
              @change=${this.triggerAutoSave}
              ?disabled=${this.isSaving}
              placeholder="mdi:room"
            />
          </div>

          <div class="form-group">
            <label>Rooms *</label>
            <div 
              class="entity-drop-zone"
              @dragover=${this.handleDragOver}
              @drop=${this.handleDrop}
            >
              ${this.formData.entities.length === 0
                ? html`<div class="drop-placeholder">Drag rooms here</div>`
                : html`
                    <div class="entity-list">
                      ${this.formData.entities.map(entity => 
                        html`
                          <div class="entity-item removable">
                            <span class="entity-domain">${entity.domain}</span>
                            <span class="entity-name">${entity.name}</span>
                            <button 
                              type="button"
                              class="btn-remove"
                              @click=${() => this.removeEntity(entity.entity_id)}
                            >
                              ✕
                            </button>
                          </div>
                        `
                      )}
                    </div>
                  `
              }
            </div>
            ${this.validationErrors.entities
              ? html`<div class="error-text">${this.validationErrors.entities}</div>`
              : nothing
            }
          </div>

          <div class="form-actions">
            <button 
              type="button"
              class="btn btn-secondary" 
              @click=${this.cancelEdit}
              ?disabled=${this.isSaving}
            >
              Cancel
            </button>
            <button 
              type="submit"
              class="btn btn-primary"
              ?disabled=${this.isSaving || !this.formData.name.trim() || this.formData.entities.length === 0}
            >
              ${this.isSaving ? html`<div class="spinner"></div>` : nothing}
              Save Changes
            </button>
          </div>
        </form>
      </div>
    `;
  }

  private renderDraggableEntity(entity: ZoneEntity) {
    return html`
      <div 
        class="draggable-entity"
        draggable="true"
        @dragstart=${(e: DragEvent) => this.handleDragStart(e, entity)}
      >
        <span class="entity-domain">${entity.domain}</span>
        <span class="entity-name">${entity.name}</span>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'zone-editor': ZoneEditor;
  }
}
