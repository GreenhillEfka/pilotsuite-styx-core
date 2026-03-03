/**
 * PilotSuite Styx - 3D Vision Module
 * Three.js Integration fuer 3D Haus-Visualisierung
 * Viewona - 3D Vision Specialist
 */

class Vision3D {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            width: options.width || 800,
            height: options.height || 600,
            backgroundColor: options.backgroundColor || 0x1a1a2e,
            showGrid: options.showGrid !== false,
            showAxes: options.showAxes !== false,
            shadows: options.shadows !== false,
            ...options
        };
        
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.raycaster = null;
        this.mouse = null;
        this.objects = [];
        this.animationId = null;
        this.hoveredObject = null;
        this.selectedObject = null;
        
        this.zoneMeshes = new Map();
        this.zoneData = new Map();
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            console.error('[Vision3D] Container not found');
            return;
        }
        
        this.setupScene();
        this.setupCamera();
        this.setupRenderer();
        this.setupLights();
        this.setupControls();
        this.setupRaycaster();
        this.setupEventListeners();
        this.createEnvironment();
        this.animate();
        
        console.log('[Vision3D] Initialized');
    }
    
    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(this.options.backgroundColor);
        this.scene.fog = new THREE.Fog(this.options.backgroundColor, 20, 100);
    }
    
    setupCamera() {
        const aspect = this.options.width / this.options.height;
        this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
        this.camera.position.set(30, 25, 30);
        this.camera.lookAt(0, 0, 0);
    }
    
    setupRenderer() {
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.options.width, this.options.height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.shadowMap.enabled = this.options.shadows;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.container.appendChild(this.renderer.domElement);
        this.canvas = this.renderer.domElement;
    }
    
    setupLights() {
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(20, 40, 20);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        const pointLight1 = new THREE.PointLight(0x60a5fa, 0.5, 50);
        pointLight1.position.set(-10, 15, -10);
        this.scene.add(pointLight1);
    }
    
    setupControls() {
        if (typeof THREE.OrbitControls === 'undefined') {
            console.warn('[Vision3D] OrbitControls not available');
            return;
        }
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.minDistance = 10;
        this.controls.maxDistance = 100;
        this.controls.maxPolarAngle = Math.PI / 2 - 0.1;
    }
    
    setupRaycaster() {
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
    }
    
    setupEventListeners() {
        window.addEventListener('resize', () => this.onWindowResize(), { passive: true });
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e), { passive: true });
        this.canvas.addEventListener('click', (e) => this.onClick(e), { passive: true });
        this.canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e), { passive: true });
    }
    
    createEnvironment() {
        if (this.options.showGrid) {
            const gridHelper = new THREE.GridHelper(60, 60, 0x3b82f6, 0x1e293b);
            this.scene.add(gridHelper);
        }
        
        if (this.options.showAxes) {
            const axesHelper = new THREE.AxesHelper(10);
            this.scene.add(axesHelper);
        }
        
        const planeGeometry = new THREE.PlaneGeometry(100, 100);
        const planeMaterial = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.8, metalness: 0.2 });
        const plane = new THREE.Mesh(planeGeometry, planeMaterial);
        plane.rotation.x = -Math.PI / 2;
        plane.position.y = -0.01;
        plane.receiveShadow = true;
        this.scene.add(plane);
    }
    
    createZone(zoneConfig) {
        const { id, name, position, size, color, sensors } = zoneConfig;
        
        const zoneGroup = new THREE.Group();
        zoneGroup.name = `zone-${id}`;
        zoneGroup.userData = { type: 'zone', id, name, ...zoneConfig };
        
        const geometry = new THREE.BoxGeometry(size.x, size.y, size.z);
        const material = new THREE.MeshStandardMaterial({
            color: color || 0x3b82f6, transparent: true, opacity: 0.7,
            roughness: 0.3, metalness: 0.1
        });
        
        const zoneMesh = new THREE.Mesh(geometry, material);
        zoneMesh.position.set(position.x, position.y + size.y / 2, position.z);
        zoneMesh.castShadow = true;
        zoneMesh.receiveShadow = true;
        zoneMesh.userData = { parentGroup: zoneGroup };
        
        zoneGroup.add(zoneMesh);
        
        const edges = new THREE.EdgesGeometry(geometry);
        const lineMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 });
        const wireframe = new THREE.LineSegments(edges, lineMaterial);
        wireframe.position.copy(zoneMesh.position);
        zoneGroup.add(wireframe);
        
        const indicatorGeometry = new THREE.SphereGeometry(0.5, 16, 16);
        const indicatorMaterial = new THREE.MeshBasicMaterial({ color: 0x22c55e, transparent: true, opacity: 0.9 });
        const indicator = new THREE.Mesh(indicatorGeometry, indicatorMaterial);
        indicator.position.set(position.x, position.y + size.y + 1, position.z);
        indicator.userData = { type: 'statusIndicator', zoneId: id };
        zoneGroup.add(indicator);
        this.zoneMeshes.set(`${id}-indicator`, indicator);
        
        this.createZoneLabel(zoneGroup, name, position, size);
        this.addZoneSensors(zoneGroup, sensors || []);
        
        this.scene.add(zoneGroup);
        this.objects.push(zoneMesh);
        this.zoneMeshes.set(id, zoneGroup);
        
        zoneGroup.scale.set(0, 0, 0);
        this.animateZoneEntry(zoneGroup);
        
        return zoneGroup;
    }
    
    createZoneLabel(zoneGroup, name, position, size) {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        
        context.fillStyle = 'rgba(15, 23, 42, 0.8)';
        context.roundRect(0, 0, 512, 128, 16);
        context.fill();
        
        context.font = 'bold 48px Arial';
        context.fillStyle = '#ffffff';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(name, 256, 64);
        
        const texture = new THREE.CanvasTexture(canvas);
        const spriteMaterial = new THREE.SpriteMaterial({ map: texture, transparent: true });
        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.position.set(position.x, position.y + size.y + 3, position.z);
        sprite.scale.set(8, 2, 1);
        zoneGroup.add(sprite);
    }
    
    addZoneSensors(zoneGroup, sensors) {
        const colors = { temperature: 0xf59e0b, humidity: 0x06b6d4, motion: 0xef4444, light: 0xfbbf24, door: 0x22c55e, window: 0x3b82f6 };
        
        sensors.forEach((sensor, index) => {
            const angle = (index / sensors.length) * Math.PI * 2;
            const radius = 2;
            const x = Math.cos(angle) * radius;
            const z = Math.sin(angle) * radius;
            
            const geometry = new THREE.ConeGeometry(0.3, 0.8, 8);
            const material = new THREE.MeshStandardMaterial({
                color: colors[sensor.type] || 0xffffff,
                emissive: colors[sensor.type] || 0xffffff,
                emissiveIntensity: 0.5
            });
            
            const sensorMesh = new THREE.Mesh(geometry, material);
            sensorMesh.position.set(x, 1, z);
            sensorMesh.userData = { type: 'sensor', ...sensor };
            zoneGroup.add(sensorMesh);
            this.animateSensorPulse(sensorMesh);
        });
    }
    
    animateZoneEntry(zoneGroup) {
        const startTime = Date.now();
        const duration = 600;
        
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            zoneGroup.scale.set(eased, eased, eased);
            if (progress < 1) requestAnimationFrame(animate);
        };
        animate();
    }
    
    animateSensorPulse(mesh) {
        const baseIntensity = 0.5;
        const pulse = () => {
            if (!mesh.parent) return;
            const time = Date.now() * 0.002;
            mesh.material.emissiveIntensity = baseIntensity + Math.sin(time) * 0.3;
            requestAnimationFrame(pulse);
        };
        pulse();
    }
    
    updateZoneData(zoneId, data) {
        const zoneGroup = this.zoneMeshes.get(zoneId);
        if (!zoneGroup) return;
        this.zoneData.set(zoneId, data);
        
        const indicator = this.zoneMeshes.get(`${zoneId}-indicator`);
        if (indicator) {
            const color = data.alertCount > 0 ? 0xef4444 : data.warningCount > 0 ? 0xf59e0b : 0x22c55e;
            indicator.material.color.setHex(color);
        }
        
        const zoneMesh = zoneGroup.children.find(c => c.userData.parentGroup === zoneGroup);
        if (zoneMesh) {
            const targetColor = data.alertCount > 0 ? 0xef4444 : data.warningCount > 0 ? 0xf59e0b : zoneGroup.userData.color || 0x3b82f6;
            zoneMesh.material.color.setHex(targetColor);
        }
    }
    
    highlightZone(zoneId, enabled = true) {
        const zoneGroup = this.zoneMeshes.get(zoneId);
        if (!zoneGroup) return;
        const zoneMesh = zoneGroup.children.find(c => c.userData.parentGroup === zoneGroup);
        if (zoneMesh) {
            zoneMesh.material.emissive.setHex(enabled ? 0x60a5fa : 0x000000);
            zoneMesh.material.emissiveIntensity = enabled ? 0.3 : 0;
        }
    }
    
    focusZone(zoneId) {
        const zoneGroup = this.zoneMeshes.get(zoneId);
        if (!zoneGroup) return;
        const position = zoneGroup.position;
        this.animateCamera({ x: position.x + 15, y: position.y + 15, z: position.z + 15 }, position);
    }
    
    animateCamera(targetPos, lookAtPos) {
        const startPos = this.camera.position.clone();
        const startTarget = this.controls ? this.controls.target.clone() : new THREE.Vector3();
        const startTime = Date.now();
        const duration = 1000;
        
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            
            this.camera.position.lerpVectors(startPos, new THREE.Vector3(targetPos.x, targetPos.y, targetPos.z), eased);
            if (this.controls) {
                this.controls.target.lerpVectors(startTarget, new THREE.Vector3(lookAtPos.x, lookAtPos.y, lookAtPos.z), eased);
                this.controls.update();
            }
            if (progress < 1) requestAnimationFrame(animate);
        };
        animate();
    }
    
    onWindowResize() {
        if (!this.container) return;
        const rect = this.container.getBoundingClientRect();
        this.options.width = rect.width;
        this.options.height = rect.height;
        this.camera.aspect = this.options.width / this.options.height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.options.width, this.options.height);
    }
    
    onMouseMove(event) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.objects);
        
        if (intersects.length > 0) {
            const zoneGroup = intersects[0].object.userData.parentGroup;
            if (this.hoveredObject !== zoneGroup) {
                if (this.hoveredObject) this.highlightZone(this.hoveredObject.userData.id, false);
                this.hoveredObject = zoneGroup;
                this.highlightZone(zoneGroup.userData.id, true);
                this.canvas.style.cursor = 'pointer';
                this.emit('zoneHover', zoneGroup.userData);
            }
        } else {
            if (this.hoveredObject) {
                this.highlightZone(this.hoveredObject.userData.id, false);
                this.hoveredObject = null;
                this.canvas.style.cursor = 'default';
            }
        }
    }
    
    onClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.objects);
        
        if (intersects.length > 0) {
            const zoneGroup = intersects[0].object.userData.parentGroup;
            this.selectedObject = zoneGroup;
            this.emit('zoneSelect', zoneGroup.userData);
        }
    }
    
    onDoubleClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.objects);
        
        if (intersects.length > 0) {
            this.focusZone(intersects[0].object.userData.parentGroup.userData.id);
        }
    }
    
    emit(eventName, data) {
        document.dispatchEvent(new CustomEvent(`vision3d:${eventName}`, { detail: data }));
    }
    
    on(eventName, callback) {
        document.addEventListener(`vision3d:${eventName}`, (e) => callback(e.detail));
    }
    
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        if (this.controls) this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
    
    resetCamera() {
        this.animateCamera({ x: 30, y: 25, z: 30 }, { x: 0, y: 0, z: 0 });
    }
    
    setTheme(theme) {
        const bgColor = theme === 'dark' ? 0x0f172a : 0xf8fafc;
        this.scene.background = new THREE.Color(bgColor);
        this.scene.fog.color = new THREE.Color(bgColor);
    }
    
    dispose() {
        if (this.animationId) cancelAnimationFrame(this.animationId);
        this.objects.forEach(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
                else obj.material.dispose();
            }
        });
        this.renderer.dispose();
        this.container.removeChild(this.canvas);
    }
}

window.Vision3D = Vision3D;
