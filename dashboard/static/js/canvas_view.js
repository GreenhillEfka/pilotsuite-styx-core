/**
 * PilotSuite Styx - Canvas/View Integration
 * Canvas-Overlay fuer 3D Vision mit DOM-Synchronisation
 * Viewona - 3D Vision Specialist
 */

class CanvasView {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            syncInterval: options.syncInterval || 16,
            showOverlays: options.showOverlays !== false,
            interactive: options.interactive !== false,
            ...options
        };
        
        this.canvas = null;
        this.ctx = null;
        this.overlayLayer = null;
        this.vision3d = null;
        this.projectedPoints = new Map();
        this.overlays = new Map();
        this.isRunning = false;
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            console.error('[CanvasView] Container not found');
            return;
        }
        this.setupCanvas();
        this.setupOverlayLayer();
        this.setupEventListeners();
        console.log('[CanvasView] Initialized');
    }
    
    setupCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'canvas-view-layer';
        this.canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10;';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.resize();
    }
    
    setupOverlayLayer() {
        this.overlayLayer = document.createElement('div');
        this.overlayLayer.className = 'canvas-overlay-layer';
        this.overlayLayer.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:20;';
        this.container.appendChild(this.overlayLayer);
    }
    
    setupEventListeners() {
        window.addEventListener('resize', () => this.resize(), { passive: true });
    }
    
    connectToVision3D(vision3dInstance) {
        this.vision3d = vision3dInstance;
        this.vision3d.on('zoneHover', (data) => this.onZoneHover(data));
        this.vision3d.on('zoneSelect', (data) => this.onZoneSelect(data));
        this.startSync();
        console.log('[CanvasView] Connected to Vision3D');
    }
    
    startSync() {
        if (this.isRunning) return;
        this.isRunning = true;
        
        const loop = () => {
            if (!this.isRunning) return;
            this.syncWith3D();
            requestAnimationFrame(loop);
        };
        loop();
    }
    
    stopSync() {
        this.isRunning = false;
    }
    
    syncWith3D() {
        if (!this.vision3d) return;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.updateProjectedPoints();
        this.updateOverlays();
        this.draw();
    }
    
    updateProjectedPoints() {
        if (!this.vision3d || !this.vision3d.camera) return;
        this.projectedPoints.clear();
        
        this.vision3d.zoneMeshes.forEach((mesh, id) => {
            if (id.endsWith('-indicator')) return;
            const worldPosition = new THREE.Vector3();
            mesh.getWorldPosition(worldPosition);
            const projected = worldPosition.clone().project(this.vision3d.camera);
            const x = (projected.x * 0.5 + 0.5) * this.canvas.width;
            const y = (-projected.y * 0.5 + 0.5) * this.canvas.height;
            this.projectedPoints.set(id, { x, y, visible: projected.z < 1, worldPosition, data: mesh.userData });
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
                <button class="overlay-close">x</button>
            </div>
            <div class="overlay-content">
                <div class="overlay-metric"><span>-- C</span></div>
                <div class="overlay-metric"><span>-- %</span></div>
            </div>
        `;
        overlay.querySelector('.overlay-close').addEventListener('click', () => { overlay.style.display = 'none'; });
        this.overlayLayer.appendChild(overlay);
        this.overlays.set(id, overlay);
        this.positionOverlay(overlay, point);
    }
    
    positionOverlay(overlay, point) {
        const rect = overlay.getBoundingClientRect();
        const x = point.x - rect.width / 2;
        const y = point.y - rect.height - 20;
        overlay.style.cssText = `position:absolute;left:${x}px;top:${y}px;display:block;pointer-events:auto;opacity:${Math.max(0.3, 1 - point.z * 0.3)}`;
    }
    
    draw() {
        this.drawZoneConnections();
        this.drawActiveRegions();
        this.drawProjectedPoints();
    }
    
    drawZoneConnections() {
        const points = Array.from(this.projectedPoints.values()).filter(p => p.visible);
        this.ctx.strokeStyle = 'rgba(59, 130, 246, 0.3)';
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([5, 5]);
        
        for (let i = 0; i < points.length; i++) {
            for (let j = i + 1; j < points.length; j++) {
                const dist = Math.sqrt(Math.pow(points[i].x - points[j].x, 2) + Math.pow(points[i].y - points[j].y, 2));
                if (dist < 150) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(points[i].x, points[i].y);
                    this.ctx.lineTo(points[j].x, points[j].y);
                    this.ctx.stroke();
                }
            }
        }
        this.ctx.setLineDash([]);
    }
    
    drawActiveRegions() {
        this.projectedPoints.forEach((point, id) => {
            if (!point.visible) return;
            const zoneData = this.vision3d?.zoneData.get(id);
            if (!zoneData) return;
            
            const activity = zoneData.activity || 0;
            if (activity > 0.5) {
                const radius = 30 + activity * 20;
                const gradient = this.ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
                gradient.addColorStop(0, `rgba(34, 197, 94, ${activity * 0.3})`);
                gradient.addColorStop(1, 'rgba(34, 197, 94, 0)');
                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
                this.ctx.fill();
            }
            
            if (zoneData.alertCount > 0) {
                this.ctx.fillStyle = '#ef4444';
                this.ctx.beginPath();
                this.ctx.arc(point.x + 25, point.y - 25, 8, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.fillStyle = '#ffffff';
                this.ctx.font = 'bold 10px Arial';
                this.ctx.textAlign = 'center';
                this.ctx.fillText(zoneData.alertCount.toString(), point.x + 25, point.y - 21);
            }
        });
    }
    
    drawProjectedPoints() {
        this.projectedPoints.forEach((point) => {
            if (!point.visible) return;
            this.ctx.fillStyle = '#22c55e';
            this.ctx.beginPath();
            this.ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
            this.ctx.fill();
        });
    }
    
    onZoneHover(data) {
        const overlay = this.overlays.get(data.id);
        if (overlay) overlay.classList.add('hovered');
    }
    
    onZoneSelect(data) {
        const overlay = this.overlays.get(data.id);
        if (overlay) {
            overlay.style.display = 'block';
            overlay.classList.add('selected');
        }
        this.emit('zoneSelected', data);
    }
    
    updateZoneMetrics(zoneId, metrics) {
        const overlay = this.overlays.get(zoneId);
        if (overlay && metrics) {
            const content = overlay.querySelector('.overlay-content');
            content.innerHTML = `
                <div class="overlay-metric"><span>${metrics.temperature || '--'} C</span></div>
                <div class="overlay-metric"><span>${metrics.humidity || '--'} %</span></div>
            `;
        }
    }
    
    resize() {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
    }
    
    emit(eventName, data) {
        document.dispatchEvent(new CustomEvent(`canvasview:${eventName}`, { detail: data }));
    }
    
    dispose() {
        this.stopSync();
        this.overlays.forEach(overlay => overlay.remove());
        this.overlays.clear();
        if (this.canvas && this.canvas.parentNode) this.canvas.parentNode.removeChild(this.canvas);
        if (this.overlayLayer && this.overlayLayer.parentNode) this.overlayLayer.parentNode.removeChild(this.overlayLayer);
    }
}

window.CanvasView = CanvasView;
