/**
 * Zone Editor Component Tests
 * 
 * Unit tests for the Zone Editor Lit Component
 * Tests cover: rendering, state management, CRUD operations,
 * drag & drop, validation, auto-save, loading states, error handling
 * 
 * @author Clawdya
 * @version 1.0.0
 */

import { html, fixture, expect, oneEvent } from '@open-wc/testing';
import { stub } from 'sinon';
import '../static/zone/zone_editor.js';
import type { ZoneEditor, Zone, ZoneEntity } from '../static/zone/zone_editor.js';

describe('ZoneEditor Component', () => {
  let element: ZoneEditor;

  beforeEach(async () => {
    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
  });

  // ============================================================================
  // Basic Rendering Tests (1-5)
  // ============================================================================

  it('1. should render the component', () => {
    expect(element).to.exist;
    expect(element.shadowRoot).to.exist;
  });

  it('2. should render the header with title', () => {
    const header = element.shadowRoot?.querySelector('.header h2');
    expect(header).to.exist;
    expect(header?.textContent).to.include('Zone Editor');
  });

  it('3. should render the "New Zone" button', () => {
    const newZoneBtn = element.shadowRoot?.querySelector('.btn-primary');
    expect(newZoneBtn).to.exist;
    expect(newZoneBtn?.textContent).to.include('New Zone');
  });

  it('4. should render empty zone list initially', () => {
    const zoneList = element.shadowRoot?.querySelector('.zone-list');
    expect(zoneList).to.exist;
    expect(zoneList?.children.length).to.equal(0);
  });

  it('5. should render empty state when no zone selected', () => {
    const emptyState = element.shadowRoot?.querySelector('.empty-state');
    expect(emptyState).to.exist;
    expect(emptyState?.textContent).to.include('Select a Zone');
  });

  // ============================================================================
  // Zone List Rendering Tests (6-10)
  // ============================================================================

  it('6. should render zone list items when zones are loaded', async () => {
    const mockZones: Zone[] = [
      {
        zone_id: 'zone:living_room',
        name: 'Living Room',
        entities: [
          { entity_id: 'light.living_room', name: 'Living Room Light', domain: 'light' }
        ],
        floor: 1,
      },
      {
        zone_id: 'zone:kitchen',
        name: 'Kitchen',
        entities: [],
        floor: 1,
      },
    ];

    // Set zones directly (simulating API load)
    (element as any).zones = mockZones;
    await element.updateComplete;

    const zoneItems = element.shadowRoot?.querySelectorAll('.zone-list-item');
    expect(zoneItems).to.have.lengthOf(2);
  });

  it('7. should display zone name in list item', async () => {
    const mockZones: Zone[] = [
      {
        zone_id: 'zone:test',
        name: 'Test Zone',
        entities: [],
      },
    ];

    (element as any).zones = mockZones;
    await element.updateComplete;

    const zoneName = element.shadowRoot?.querySelector('.zone-name');
    expect(zoneName?.textContent).to.equal('Test Zone');
  });

  it('8. should display entity count in zone list', async () => {
    const mockZones: Zone[] = [
      {
        zone_id: 'zone:test',
        name: 'Test Zone',
        entities: [
          { entity_id: 'light.1', name: 'Light 1', domain: 'light' },
          { entity_id: 'light.2', name: 'Light 2', domain: 'light' },
          { entity_id: 'sensor.1', name: 'Sensor 1', domain: 'sensor' },
        ],
      },
    ];

    (element as any).zones = mockZones;
    await element.updateComplete;

    const zoneMeta = element.shadowRoot?.querySelector('.zone-meta');
    expect(zoneMeta?.textContent).to.include('3 entities');
  });

  it('9. should highlight selected zone', async () => {
    const mockZones: Zone[] = [
      {
        zone_id: 'zone:selected',
        name: 'Selected Zone',
        entities: [],
      },
      {
        zone_id: 'zone:other',
        name: 'Other Zone',
        entities: [],
      },
    ];

    (element as any).zones = mockZones;
    (element as any).selectedZone = mockZones[0];
    await element.updateComplete;

    const zoneItems = element.shadowRoot?.querySelectorAll('.zone-list-item');
    expect(zoneItems?.[0].classList.contains('selected')).to.be.true;
    expect(zoneItems?.[1].classList.contains('selected')).to.be.false;
  });

  it('10. should show floor information when available', async () => {
    const mockZones: Zone[] = [
      {
        zone_id: 'zone:test',
        name: 'Test Zone',
        entities: [],
        floor: 2,
      },
    ];

    (element as any).zones = mockZones;
    await element.updateComplete;

    const zoneMeta = element.shadowRoot?.querySelector('.zone-meta');
    expect(zoneMeta?.textContent).to.include('Floor 2');
  });

  // ============================================================================
  // Loading State Tests (11-14)
  // ============================================================================

  it('11. should show skeleton loading state when isLoading is true', async () => {
    (element as any).isLoading = true;
    (element as any).zones = [];
    await element.updateComplete;

    const skeletonList = element.shadowRoot?.querySelector('.skeleton-list');
    expect(skeletonList).to.exist;
  });

  it('12. should hide skeleton when loading completes', async () => {
    (element as any).isLoading = true;
    await element.updateComplete;

    let skeletonList = element.shadowRoot?.querySelector('.skeleton-list');
    expect(skeletonList).to.exist;

    (element as any).isLoading = false;
    (element as any).zones = [];
    await element.updateComplete;

    skeletonList = element.shadowRoot?.querySelector('.skeleton-list');
    expect(skeletonList).to.not.exist;
  });

  it('13. should show spinner in button when saving', async () => {
    (element as any).isSaving = true;
    (element as any).showCreateForm = true;
    await element.updateComplete;

    const spinner = element.shadowRoot?.querySelector('.spinner');
    expect(spinner).to.exist;
  });

  it('14. should disable buttons during save operation', async () => {
    (element as any).isSaving = true;
    (element as any).showCreateForm = true;
    await element.updateComplete;

    const submitBtn = element.shadowRoot?.querySelector('button[type="submit"]');
    expect(submitBtn?.hasAttribute('disabled')).to.be.true;
  });

  // ============================================================================
  // Form Tests (15-19)
  // ============================================================================

  it('15. should show create form when startCreateMode is called', async () => {
    element.startCreateMode();
    await element.updateComplete;

    const formContainer = element.shadowRoot?.querySelector('.form-container');
    expect(formContainer).to.exist;

    const formHeader = formContainer?.querySelector('.form-header h3');
    expect(formHeader?.textContent).to.include('Create New Zone');
  });

  it('16. should show edit form when startEditMode is called', async () => {
    (element as any).selectedZone = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      entities: [],
      floor: 1,
    };

    element.startEditMode();
    await element.updateComplete;

    const formContainer = element.shadowRoot?.querySelector('.form-container');
    expect(formContainer).to.exist;

    const formHeader = formContainer?.querySelector('.form-header h3');
    expect(formHeader?.textContent).to.include('Edit Zone');
  });

  it('17. should populate form with zone data in edit mode', async () => {
    const testZone: Zone = {
      zone_id: 'zone:edit_test',
      name: 'Edit Test Zone',
      entities: [],
      floor: 3,
      area_sqm: 25.5,
      icon: 'mdi:sofa',
    };

    (element as any).selectedZone = testZone;
    element.startEditMode();
    await element.updateComplete;

    const nameInput = element.shadowRoot?.querySelector('#edit_name') as HTMLInputElement;
    const floorInput = element.shadowRoot?.querySelector('#edit_floor') as HTMLInputElement;
    const areaInput = element.shadowRoot?.querySelector('#edit_area_sqm') as HTMLInputElement;
    const iconInput = element.shadowRoot?.querySelector('#edit_icon') as HTMLInputElement;

    expect(nameInput?.value).to.equal('Edit Test Zone');
    expect(floorInput?.value).to.equal('3');
    expect(areaInput?.value).to.equal('25.5');
    expect(iconInput?.value).to.equal('mdi:sofa');
  });

  it('18. should disable zone_id input in edit mode', async () => {
    (element as any).selectedZone = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      entities: [],
    };

    element.startEditMode();
    await element.updateComplete;

    const zoneIdInput = element.shadowRoot?.querySelector('#edit_zone_id') as HTMLInputElement;
    expect(zoneIdInput?.disabled).to.be.true;
  });

  it('19. should reset form when cancelEdit is called', async () => {
    (element as any).selectedZone = {
      zone_id: 'zone:test',
      name: 'Original Name',
      entities: [],
    };

    element.startEditMode();
    await element.updateComplete;

    // Change form data
    (element as any).formData.name = 'Modified Name';
    await element.updateComplete;

    // Cancel edit
    element.cancelEdit();
    await element.updateComplete;

    expect((element as any).editMode).to.be.false;
  });

  // ============================================================================
  // Validation Tests (20-24)
  // ============================================================================

  it('20. should validate that name is required', () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: '',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    const isValid = element.validateForm();
    expect(isValid).to.be.false;
    expect((element as any).validationErrors.name).to.exist;
  });

  it('21. should validate that at least one room is required', () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [],
    };

    const isValid = element.validateForm();
    expect(isValid).to.be.false;
    expect((element as any).validationErrors.entities).to.exist;
    expect((element as any).validationErrors.entities).to.include('at least one room');
  });

  it('22. should validate zone_id is required for creation', () => {
    (element as any).selectedZone = null;
    (element as any).formData = {
      zone_id: '',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    const isValid = element.validateForm();
    expect(isValid).to.be.false;
    expect((element as any).validationErrors.zone_id).to.exist;
  });

  it('23. should clear validation error when field is updated', async () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: '',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    element.validateForm();
    expect((element as any).validationErrors.name).to.exist;

    element.handleFormInput('name', 'Valid Name');
    await element.updateComplete;

    expect((element as any).validationErrors.name).to.not.exist;
  });

  it('24. should return true when all validations pass', () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Valid Zone',
      floor: 1,
      area_sqm: 20.5,
      icon: 'mdi:room',
      entities: [
        { entity_id: 'light.1', name: 'Light 1', domain: 'light' },
        { entity_id: 'sensor.1', name: 'Sensor 1', domain: 'sensor' },
      ],
    };

    const isValid = element.validateForm();
    expect(isValid).to.be.true;
    expect(Object.keys((element as any).validationErrors).length).to.equal(0);
  });

  // ============================================================================
  // Drag & Drop Tests (25-28)
  // ============================================================================

  it('25. should set draggedEntity on drag start', () => {
    const testEntity: ZoneEntity = {
      entity_id: 'light.test',
      name: 'Test Light',
      domain: 'light',
    };

    const mockEvent = {
      dataTransfer: {
        setData: stub(),
        effectAllowed: '',
      },
    } as unknown as DragEvent;

    element.handleDragStart(mockEvent, testEntity);

    expect((element as any).draggedEntity).to.deep.equal({
      entity_id: 'light.test',
      name: 'Test Light',
      domain: 'light',
    });
    expect(mockEvent.dataTransfer?.setData).calledWith(
      'text/plain',
      JSON.stringify((element as any).draggedEntity)
    );
  });

  it('26. should prevent default on drag over', () => {
    const mockEvent = {
      preventDefault: stub(),
      dataTransfer: { dropEffect: '' },
    } as unknown as DragEvent;

    element.handleDragOver(mockEvent);

    expect(mockEvent.preventDefault).calledOnce;
    expect(mockEvent.dataTransfer?.dropEffect).to.equal('copy');
  });

  it('27. should add entity to form on drop', async () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [],
    };

    const mockEvent = {
      preventDefault: stub(),
      dataTransfer: {
        getData: stub().returns(JSON.stringify({
          entity_id: 'light.dropped',
          name: 'Dropped Light',
          domain: 'light',
        })),
      },
    } as unknown as DragEvent;

    element.handleDrop(mockEvent);
    await element.updateComplete;

    expect((element as any).formData.entities).to.have.lengthOf(1);
    expect((element as any).formData.entities[0].entity_id).to.equal('light.dropped');
  });

  it('28. should not add duplicate entity on drop', async () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [
        { entity_id: 'light.existing', name: 'Existing Light', domain: 'light' },
      ],
    };

    const mockEvent = {
      preventDefault: stub(),
      dataTransfer: {
        getData: stub().returns(JSON.stringify({
          entity_id: 'light.existing',
          name: 'Existing Light',
          domain: 'light',
        })),
      },
    } as unknown as DragEvent;

    element.handleDrop(mockEvent);
    await element.updateComplete;

    expect((element as any).formData.entities).to.have.lengthOf(1);
  });

  // ============================================================================
  // Entity Management Tests (29-31)
  // ============================================================================

  it('29. should remove entity from form', async () => {
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [
        { entity_id: 'light.1', name: 'Light 1', domain: 'light' },
        { entity_id: 'light.2', name: 'Light 2', domain: 'light' },
      ],
    };

    element.removeEntity('light.1');
    await element.updateComplete;

    expect((element as any).formData.entities).to.have.lengthOf(1);
    expect((element as any).formData.entities[0].entity_id).to.equal('light.2');
  });

  it('30. should render draggable entities in available entities panel', async () => {
    (element as any).showCreateForm = true;
    await element.updateComplete;

    const draggableEntities = element.shadowRoot?.querySelectorAll('.draggable-entity');
    expect(draggableEntities).to.have.length.greaterThan(0);
  });

  it('31. should render entity drop zone in form', async () => {
    (element as any).showCreateForm = true;
    await element.updateComplete;

    const dropZone = element.shadowRoot?.querySelector('.entity-drop-zone');
    expect(dropZone).to.exist;
  });

  // ============================================================================
  // Success/Error Message Tests (32-34)
  // ============================================================================

  it('32. should show success message', async () => {
    (element as any).successMessage = 'Zone created successfully';
    await element.updateComplete;

    const successMsg = element.shadowRoot?.querySelector('.message.success');
    expect(successMsg).to.exist;
    expect(successMsg?.textContent).to.include('Zone created successfully');
  });

  it('33. should show error message', async () => {
    (element as any).error = 'Failed to load zones';
    await element.updateComplete;

    const errorMsg = element.shadowRoot?.querySelector('.message.error');
    expect(errorMsg).to.exist;
    expect(errorMsg?.textContent).to.include('Failed to load zones');
  });

  it('34. should clear success message after timeout', (done) => {
    (element as any).successMessage = 'Test message';
    
    setTimeout(() => {
      expect((element as any).successMessage).to.be.null;
      done();
    }, 3100);
  });

  // ============================================================================
  // Auto-Save Tests (35-36)
  // ============================================================================

  it('35. should trigger auto-save after debounce', (done) => {
    (element as any).editMode = true;
    (element as any).selectedZone = { zone_id: 'zone:test', name: 'Test', entities: [] };
    
    const updateZoneStub = stub(element, 'updateZone' as any).callsFake(() => {
      expect(true).to.be.true;
      done();
    });

    element.triggerAutoSave();

    // Auto-save should trigger after 1 second
  });

  it('36. should clear previous auto-save timeout on new trigger', () => {
    const clearTimeoutSpy = stub(window, 'clearTimeout');
    
    element.triggerAutoSave();
    element.triggerAutoSave();

    expect(clearTimeoutSpy.calledOnce).to.be.true;
    
    clearTimeoutSpy.restore();
  });

  // ============================================================================
  // API Configuration Tests (37-38)
  // ============================================================================

  it('37. should use custom API base URL', async () => {
    element.apiBaseUrl = '/custom/api/zone';
    await element.updateComplete;

    expect(element.apiBaseUrl).to.equal('/custom/api/zone');
  });

  it('38. should include auth token in headers', () => {
    element.authToken = 'test-token-123';
    
    const headers = (element as any).getHeaders();
    expect(headers['Authorization']).to.equal('Bearer test-token-123');
    expect(headers['Content-Type']).to.equal('application/json');
  });

  // ============================================================================
  // Zone Detail Rendering Tests (39-40)
  // ============================================================================

  it('39. should render zone detail view', async () => {
    (element as any).selectedZone = {
      zone_id: 'zone:detail_test',
      name: 'Detail Test Zone',
      entities: [
        { entity_id: 'light.1', name: 'Light 1', domain: 'light' },
      ],
      floor: 2,
      area_sqm: 30.5,
    };
    await element.updateComplete;

    const zoneDetail = element.shadowRoot?.querySelector('.zone-detail');
    expect(zoneDetail).to.exist;

    const title = zoneDetail?.querySelector('h3');
    expect(title?.textContent).to.equal('Detail Test Zone');
  });

  it('40. should show edit and delete buttons in detail view', async () => {
    (element as any).selectedZone = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      entities: [],
    };
    await element.updateComplete;

    const editBtn = element.shadowRoot?.querySelector('.detail-actions .btn-secondary');
    const deleteBtn = element.shadowRoot?.querySelector('.detail-actions .btn-danger');

    expect(editBtn).to.exist;
    expect(deleteBtn).to.exist;
    expect(editBtn?.textContent).to.include('Edit');
    expect(deleteBtn?.textContent).to.include('Delete');
  });
});

// ============================================================================
// Integration Tests (Mocked API)
// ============================================================================

describe('ZoneEditor API Integration', () => {
  let element: ZoneEditor;
  let fetchStub: any;

  beforeEach(() => {
    fetchStub = stub(window, 'fetch');
  });

  afterEach(() => {
    fetchStub.restore();
  });

  it('41. should load zones from API on firstUpdated', async () => {
    const mockResponse = {
      ok: true,
      zones: [
        { zone_id: 'zone:1', name: 'Zone 1', rooms: [] },
        { zone_id: 'zone:2', name: 'Zone 2', rooms: [] },
      ],
    };

    fetchStub.resolves({
      ok: true,
      json: async () => mockResponse,
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    // Wait for firstUpdated to complete
    await new Promise(resolve => setTimeout(resolve, 100));

    expect(fetchStub.calledWith('/api/v1/zone-editor/zones', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })).to.be.true;
  });

  it('42. should handle API error on zone load', async () => {
    fetchStub.resolves({
      ok: false,
      status: 500,
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    await new Promise(resolve => setTimeout(resolve, 100));

    expect((element as any).error).to.exist;
  });

  it('43. should create zone via API', async () => {
    fetchStub.resolves({
      ok: true,
      json: async () => ({ ok: true }),
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    (element as any).formData = {
      zone_id: 'zone:new',
      name: 'New Zone',
      floor: 1,
      area_sqm: 20,
      icon: 'mdi:room',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    await (element as any).createZone();

    expect(fetchStub.calledWith('/api/v1/zone-editor/zones', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...((element as any).formData),
        rooms: ['light.1'],
      }),
    })).to.be.true;
  });

  it('44. should update zone via API', async () => {
    fetchStub.resolves({
      ok: true,
      json: async () => ({ ok: true }),
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    (element as any).selectedZone = { zone_id: 'zone:update', name: 'Update Zone', entities: [] };
    (element as any).formData = {
      zone_id: 'zone:update',
      name: 'Updated Zone',
      floor: 2,
      area_sqm: 25,
      icon: 'mdi:sofa',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    await (element as any).updateZone();

    expect(fetchStub.calledWith('/api/v1/zone-editor/zones/zone:update', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...((element as any).formData),
        rooms: ['light.1'],
      }),
    })).to.be.true;
  });

  it('45. should delete zone via API', async () => {
    fetchStub.resolves({
      ok: true,
      json: async () => ({ ok: true }),
    });

    // Stub confirm dialog
    const confirmStub = stub(window, 'confirm').returns(true);

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    await (element as any).deleteZone('zone:delete');

    expect(fetchStub.calledWith('/api/v1/zone-editor/zones/zone:delete', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })).to.be.true;

    confirmStub.restore();
  });

  it('46. should add entity to zone via API', async () => {
    fetchStub.resolves({
      ok: true,
      json: async () => ({ ok: true }),
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    const testEntity: ZoneEntity = {
      entity_id: 'light.new',
      name: 'New Light',
      domain: 'light',
    };

    await (element as any).addEntityToZone('zone:test', testEntity);

    expect(fetchStub.calledWith('/api/v1/zone-editor/zones/zone:test/rooms', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ entity_id: 'light.new' }),
    })).to.be.true;
  });

  it('47. should handle validation error on create', async () => {
    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    (element as any).formData = {
      zone_id: '',
      name: '',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [],
    };

    const result = await (element as any).createZone();
    
    expect(result).to.be.undefined; // Should return early due to validation
    expect(fetchStub.called).to.be.false; // Should not call API
  });

  it('48. should load zone details from API', async () => {
    const mockZone: Zone = {
      zone_id: 'zone:detail',
      name: 'Detail Zone',
      entities: [],
      floor: 1,
    };

    fetchStub.resolves({
      ok: true,
      json: async () => ({ ok: true, zone: mockZone }),
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    await (element as any).loadZoneDetails('zone:detail');

    expect(fetchStub.calledWith('/api/v1/zone-editor/zones/zone:detail', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })).to.be.true;
    expect((element as any).selectedZone).to.deep.equal({
      ...mockZone,
      rooms: [],
    });
  });

  it('49. should handle API error on create', async () => {
    fetchStub.resolves({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Invalid zone data' }),
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    await (element as any).createZone();

    expect((element as any).error).to.include('Invalid zone data');
  });

  it('50. should show success message after successful create', async () => {
    fetchStub.resolves({
      ok: true,
      json: async () => ({ ok: true }),
    });

    element = await fixture<ZoneEditor>(html`<zone-editor></zone-editor>`);
    
    (element as any).formData = {
      zone_id: 'zone:test',
      name: 'Test Zone',
      floor: 1,
      area_sqm: 0,
      icon: 'mdi:room',
      entities: [{ entity_id: 'light.1', name: 'Light', domain: 'light' }],
    };

    await (element as any).createZone();

    expect((element as any).successMessage).to.equal('Zone created successfully');
  });
});
