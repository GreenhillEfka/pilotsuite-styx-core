"""P6-004: Mobile Optimization — Responsive, PWA, Touch-Optimized."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PWAConfig:
    """Progressive Web App configuration."""
    name: str = "PilotSuite"
    short_name: str = "Pilot"
    description: str = "Smart Home Control"
    start_url: str = "/"
    display: str = "standalone"
    background_color: str = "#1a1a2e"
    theme_color: str = "#4a90d9"
    icons: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ResponsiveBreakpoint:
    """Responsive design breakpoint."""
    name: str
    min_width: int
    max_width: int
    columns: int
    card_width: str


class MobileOptimizer:
    """Mobile optimization for web UI."""

    def __init__(self):
        self._breakpoints = [
            ResponsiveBreakpoint("mobile", 0, 640, 1, "100%"),
            ResponsiveBreakpoint("tablet", 641, 1024, 2, "48%"),
            ResponsiveBreakpoint("desktop", 1025, 1440, 3, "32%"),
            ResponsiveBreakpoint("large", 1441, 9999, 4, "24%"),
        ]
        self._touch_gestures: Dict[str, callable] = {}
        self._pwa_config: Optional[PWAConfig] = None

    def configure_pwa(self, config: PWAConfig):
        """Configure PWA settings."""
        self._pwa_config = config
        logger.info(f"PWA configured: {config.name}")

    def generate_manifest(self) -> Dict[str, Any]:
        """Generate PWA manifest."""
        if not self._pwa_config:
            self._pwa_config = PWAConfig()
        
        return {
            "name": self._pwa_config.name,
            "short_name": self._pwa_config.short_name,
            "description": self._pwa_config.description,
            "start_url": self._pwa_config.start_url,
            "display": self._pwa_config.display,
            "background_color": self._pwa_config.background_color,
            "theme_color": self._pwa_config.theme_color,
            "icons": self._pwa_config.icons or [
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ]
        }

    def generate_service_worker(self) -> str:
        """Generate service worker script."""
        return '''
// PilotSuite Service Worker
const CACHE_NAME = 'pilotsuite-v1';
const ASSETS = [
  '/',
  '/index.html',
  '/styles.css',
  '/app.js',
  '/icon-192.png',
  '/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
});
'''

    def get_responsive_css(self) -> str:
        """Generate responsive CSS."""
        css = []
        css.append("/* Responsive Grid */")
        css.append(".dashboard-grid {")
        css.append("  display: grid;")
        css.append("  gap: 16px;")
        css.append("  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));")
        css.append("}")
        css.append("")
        
        for bp in self._breakpoints:
            css.append(f"/* {bp.name}: {bp.min_width}-{bp.max_width}px */")
            css.append(f"@media (max-width: {bp.max_width}px) {{")
            css.append(f"  .dashboard-grid {{ grid-template-columns: repeat({bp.columns}, 1fr); }}")
            css.append(f"  .card {{ width: {bp.card_width}; }}")
            css.append("}")
            css.append("")
        
        # Touch optimizations
        css.append("/* Touch Optimizations */")
        css.append("@media (hover: none) and (pointer: coarse) {")
        css.append("  button, .card-action { min-height: 44px; min-width: 44px; }")
        css.append("  .touch-feedback:active { opacity: 0.7; }")
        css.append("}")
        
        return "\n".join(css)

    def register_touch_gesture(self, gesture: str, handler: callable):
        """Register touch gesture handler."""
        self._touch_gestures[gesture] = handler
        logger.info(f"Registered touch gesture: {gesture}")

    def get_touch_gestures_js(self) -> str:
        """Generate touch gesture handling JS."""
        return '''
// Touch Gesture Handling
class TouchGestures {
  constructor(element) {
    this.element = element;
    this.touchStartX = 0;
    this.touchStartY = 0;
    this.setupListeners();
  }

  setupListeners() {
    this.element.addEventListener('touchstart', (e) => {
      this.touchStartX = e.touches[0].clientX;
      this.touchStartY = e.touches[0].clientY;
    });

    this.element.addEventListener('touchend', (e) => {
      const deltaX = e.changedTouches[0].clientX - this.touchStartX;
      const deltaY = e.changedTouches[0].clientY - this.touchStartY;
      
      if (Math.abs(deltaX) > Math.abs(deltaY)) {
        if (deltaX > 50) this.onSwipe('right');
        else if (deltaX < -50) this.onSwipe('left');
      } else {
        if (deltaY > 50) this.onSwipe('down');
        else if (deltaY < -50) this.onSwipe('up');
      }
    });
  }

  onSwipe(direction) {
    console.log('Swipe:', direction);
  }
}
'''

    def optimize_for_mobile(self) -> Dict[str, Any]:
        """Get mobile optimization settings."""
        return {
            "viewport": "width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no",
            "meta_theme_color": "#4a90d9",
            "apple_touch_icon": "/icon-192.png",
            "mask_icon": "/icon-192.png",
            "mask_icon_color": "#4a90d9",
            "format_detection": "telephone=no",
            "touch_action": "manipulation",
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            "breakpoints": len(self._breakpoints),
            "pwa_configured": self._pwa_config is not None,
            "touch_gestures": len(self._touch_gestures),
        }


# Global default optimizer
default_mobile_optimizer: Optional[MobileOptimizer] = None


def init_mobile_optimizer() -> MobileOptimizer:
    """Initialize global mobile optimizer."""
    global default_mobile_optimizer
    default_mobile_optimizer = MobileOptimizer()
    return default_mobile_optimizer
