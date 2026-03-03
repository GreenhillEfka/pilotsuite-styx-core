/**
 * PilotSuite Styx - Canvas/View Integration
 * Canvas-Overlay für 3D Vision mit DOM-Element-Synchronisation
 * Viewona - 3D Vision Specialist
 */

class CanvasView {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            syncInterval: options.syncInterval || 16, // 60fps
            showOverlays: options.showOverlays !== false,
            interactive: options.interactive !== false,
            ...options
        };
        
        this.canvas = null;
        this.ctx = null;
        this.overlayLayer = null;
        this.isRunning = false;
        this.animationFrame = null;
        this.lastSyncTime = 0;
        
        // 3D Referenz
        this.vision3d = null;
        this.projectedPoints = new Map();
        
        // Overlay-Elemente
        this.overlays = new Map();
        this.annotations = [];
        
        // Interaktions-Status
        this.isDragging = false;
        this.dragStart = { x: 0, y: 0 };
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            console.error(`[CanvasView] Container #${this.containerId} not found`);
            return;
        }
        
        this.setupCanvas();
        this.setupOverlayLayer();
        this.setupEventListeners();
        
        console.log('[CanvasView] Initialized');
    }
    
    setupCanvas() {
        // Canvas-Element erstellen
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'canvas-view-layer';
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: ${this.options.interactive ? 'auto' : 'none'};
            z-index: 10;
        `;
        
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        
        // Initial sizing
        this.resize();
    }
    
    setupOverlayLayer() {
        this.overlayLayer = document.createElement('div');
        this.overlayLayer.className = 'canvas-overlay-layer';
        this.overlayLayer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 20;
        `;
        
        this.container.appendChild(this.overlayLayer);
    }
    
    setupEventListeners() {
        if (!this.options.interactive) return;
        
        // Canvas-Events
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });
        
        // Resize
        window.addEventListener('resize', () => this.resize(), { passive: true });
    }
    
    // 3D Vision Verbindung
    connectToVision3D(vision3dInstance) {
        this.vision3d = vision3dInstance;
        
        // Events von Vision3D hören
        this.vision3d.on('zoneHover', (data) => this.onZoneHover(data));
        this.vision3d.on('zoneSelect', (data) => this.onZoneSelect(data));
        
        // Sync-Loop starten
        this.startSync();
        
        console.log('[CanvasView] Connected to Vision3D');
    }
    
    startSync() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        this.syncLoop();
    }
    
    stopSync() {
        this.isRunning = false;
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
    }
    
    syncLoop() {
        if (!this.isRunning) return;
        
        const now = performance.now();
        if (now - this.lastSyncTime >= this.options.syncInterval) {
            this.syncWith3D();
            this.lastSyncTime = now;
        }
        
        this.animationFrame = requestAnimationFrame(() => this.syncLoop());
    }
    
    syncWith3D() {
        if (!this.vision3d) return;
        
        // Canvas clearen
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Projizierte Punkte aktualisieren
        this.updateProjectedPoints();
        
        // Overlay-Elemente aktualisieren
        this.updateOverlays();
        
        // Zeichnen
        this.draw();
    }
    
    updateProjectedPoints() {
        if (!this.vision3d || !this.vision3d.camera) return;
        
        this.projectedPoints.clear();
        
        // Alle 3D-Objekte projizieren
        this.vision3d.zoneMeshes.forEach((mesh, id) => {
            if (id.endsWith('-indicator')) return;
            
            const worldPosition = new THREE.Vector3();
            mesh.getWorldPosition(worldPosition);
            
            // Projektion auf Bildschirm
            const projected = worldPosition.clone().project(this.vision3d.camera);
            
            // Auf Canvas-Koordinaten umrechnen
            const x = (projected.x * 0.5 + 0.5) * this.canvas.width;
            const y = (-projected.y * 0.5 + 0.5) * this.canvas.height;
            
            // Sichtbarkeit prüfen (nur wenn vor der Kamera)
            const isVisible = projected.z < 1;
            
            this.projectedPoints.set(id, {
                x, y,
                z: projected.z,
                visible: isVisible,
                worldPosition,
                data: mesh.userData
            });
        });
    }
    
    updateOverlays() {
        this.projectedPoints.forEach((point, id) => {
            const overlay = this.overlays.get(id);
            
            if (!point.visible) {
                if (overlay) overlay.style.display = 'none';
                return;
            }
            
            if (!overlay) {
                this.createOverlay(id, point);
            } else {
                this.positionOverlay(overlay, point);
            }
        });
    }
    
    createOverlay(id, point) {
        const overlay = document.createElement('div');
        overlay.className = 'canvas-view-overlay';
        overlay.dataset.zoneId = id;
        overlay.innerHTML = `
            <div class="overlay-header">
                <span class="overlay-title">${point.data.name || id}</span>
                <button class="overlay-close">×</button>
            </div>
            <div class="overlay-content">
                <div class="overlay-metric">
                    <i class="mdi mdi-thermometer"></i>
                    <span>--°C</span>
                </div>
                <div class="overlay-metric">
                    <i class="mdi mdi-water-percent"></i>
                    <span>--%</span>
                </div>
            </div>
        `;
        
        // Event-Listener
        overlay.querySelector('.overlay-close').addEventListener('click', () => {
            overlay.style.display = 'none';
        });
        
        this.overlayLayer.appendChild(overlay);
        this.overlays.set(id, overlay);
        
        this.positionOverlay(overlay, point);
    }
    
    positionOverlay(overlay, point) {
        const rect = overlay.getBoundingClientRect();
        const x = point.x - rect.width / 2;
        const y = point.y - rect.height - 20;
        
        overlay.style.cssText = `
            position: absolute;
            left: ${x}px;
            top: ${y}px;
            display: block;
            pointer-events: auto;
        `;
        
        // Sichtbarkeit basierend auf Z
        const opacity = Math.max(0.3, 1 - point.z * 0.3);
        overlay.style.opacity = opacity;
    }
    
    draw() {
        if (!this.ctx) return;
        
        // Verbindungslinien zwischen Zonen zeichnen
        this.drawZoneConnections();
        
        // Aktive Bereiche markieren
        this.drawActiveRegions();
        
        // Annotationen zeichnen
        this.drawAnnotations();
        
        // Debug-Info (optional)
        // this.drawDebugInfo();
    }
    
    drawZoneConnections() {
        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(59, 130, 246, 0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        
        const points = Array.from(this.projectedPoints.values())
            .filter(p => p.visible);
        
        // Verbinde nahe Zonen
        for (let i = 0; i < points.length; i++) {
            for (let j = i + 1; j < points.length; j++) {
                const dist = this.distance(points[i], points[j]);
                if (dist < 150) {
                    ctx.beginPath();
                    ctx.moveTo(points[i].x, points[i].y);
                    ctx.lineTo(points[j].x, points[j].y);
                    ctx.stroke();
                }
            }
        }
        
        ctx.setLineDash([]);
    }
    
    drawActiveRegions() {
        const ctx = this.ctx;
        
        this.projectedPoints.forEach((point, id) => {
            if (!point.visible) return;
            
            const zoneData = this.vision3d?.zoneData.get(id);
            if (!zoneData) return;
            
            // Aktive Bereiche basierend auf Sensor-Daten
            const activity = zoneData.activity || 0;
            if (activity > 0.5) {
                const radius = 30 + activity * 20;
                const gradient = ctx.createRadialGradient(
                    point.x, point.y, 0,
                    point.x, point.y, radius
                );
                gradient.addColorStop(0, `rgba(34, 197, 94, ${activity * 0.3})`);
                gradient.addColorStop(1, 'rgba(34, 197, 94, 0)');
                
                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
                ctx.fill();
            }
            
            // Alerts anzeigen
            if (zoneData.alertCount > 0) {
                ctx.fillStyle = '#ef4444';
                ctx.beginPath();
                ctx.arc(point.x + 25, point.y - 25, 8, 0, Math.PI * 2);
                ctx.fill();
                
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 10px Arial';
                ctx.textAlign = 'center';
                ctx.fillText(zoneData.alertCount.toString(), point.x + 25, point.y - 21);
            }
        });
    }
    
    drawAnnotations() {
        const ctx = this.ctx;
        
        this.annotations.forEach(anno => {
            if (!anno.visible) return;
            
            ctx.fillStyle = 'rgba(245, 158, 11, 0.9)';
            ctx.strokeStyle = '#f59e0b';
            ctx.lineWidth = 2;
            
            // Annotation-Pin
            ctx.beginPath();
            ctx.arc(anno.x, anno.y, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            
            // Label
            if (anno.label) {
                ctx.fillStyle = '#1e293b';
                ctx.font = '12px Arial';
                ctx.fillText(anno.label, anno.x + 10, anno.y);
            }
        });
    }
    
    drawDebugInfo() {
        const ctx = this.ctx;
        ctx.fillStyle = '#22c55e';
        ctx.font = '12px monospace';
        
        const info = [
            `Projected Points: ${this.projectedPoints.size}`,
            `Overlays: ${this.overlays.size}`,
            `Annotations: ${this.annotations.length}`
        ];
        
        info.forEach((line, i) => {
            ctx.fillText(line, 10, 20 + i * 16);
        });
    }
    
    // Event Handlers
    onMouseDown(e) {
        this.isDragging = true;
        this.dragStart = { x: e.clientX, y: e.clientY };
    }
    
    onMouseMove(e) {
        if (!this.isDragging) return;
        
        const dx = e.clientX - this.dragStart.x;
        const dy = e.clientY - this.dragStart.y;
        
        // Verschiebe-Logik hier implementieren
        this.dragStart = { x: e.clientX, y: e.clientY };
    }
    
    onMouseUp(e) {
        this.isDragging = false;
    }
    
    onWheel(e) {
        e.preventDefault();
        // Zoom-Logik hier
    }
    
    onZoneHover(data) {
        // Hover-Highlight im Canvas
        const overlay = this.overlays.get(data.id);
        if (overlay) {
            overlay.classList.add('hovered');
        }
    }
    
    onZoneSelect(data) {
        // Zone ausgewählt - Overlay zeigen
        const overlay = this.overlays.get(data.id);
        if (overlay) {
            overlay.style.display = 'block';
            overlay.classList.add('selected');
        }
        
        this.emit('zoneSelected', data);
    }
    
    // Public API
    addAnnotation(x, y, label = '') {
        this.annotations.push({ x, y, label, visible: true });
    }
    
    clearAnnotations() {
        this.annotations = [];
    }
    
    updateZoneMetrics(zoneId, metrics) {
        const overlay = this.overlays.get(zoneId);
        if (!overlay) return;
        
        const content = overlay.querySelector('.overlay-content');
        if (content && metrics) {
            content.innerHTML = `
                <div class="overlay-metric">
                    <i class="mdi mdi-thermometer"></i>
                    <span>${metrics.temperature || '--'}°C</span>
                </div>
                <div class="overlay-metric">
                    <i class="mdi mdi-water-percent"></i>
                    <span>${metrics.humidity || '--'}%</span>
                </div>
                ${metrics.lights ? `
                <div class="overlay-metric">
                    <i class="mdi mdi-lightbulb"></i>
                    <span>${metrics.lights} lights</span>
                </div>` : ''}
            `;
        }
    }
    
    showOverlay(zoneId) {
        const overlay = this.overlays.get(zoneId);
        if (overlay) {
            overlay.style.display = 'block';
        }
    }
    
    hideOverlay(zoneId) {
        const overlay = this.overlays.get(zoneId);
        if (overlay) {
            overlay.style.display = 'none';
        }
    }
    
    resize() {
        if (!this.container || !this.canvas) return;
        
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        // Canvas-Styles aktualisieren
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
    }
    
    distance(p1, p2) {
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    emit(eventName, data) {
        const event = new CustomEvent(`canvasview:${eventName}`, { detail: data });
        document.dispatchEvent(event);
    }
    
    on(eventName, callback) {
        document.addEventListener(`canvasview:${eventName}`, (e) => callback(e.detail));
    }
    
    dispose() {
        this.stopSync();
        
        // Overlays entfernen
        this.overlays.forEach(overlay => overlay.remove());
        this.overlays.clear();
        
        // Canvas entfernen
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        
        // Overlay-Layer entfernen
        if (this.overlayLayer && this.overlayLayer.parentNode) {
            this.overlayLayer.parentNode.removeChild(this.overlayLayer);
        }
    }
}

// Export
window.CanvasView = CanvasView;
