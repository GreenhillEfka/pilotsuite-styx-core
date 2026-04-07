"""P6-006: Dark/Light Theme — Auto-Switch, User Preference."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ThemeColors:
    """Theme color palette."""
    # Primary
    primary: str = "#4a90d9"
    primary_dark: str = "#3a7bc8"
    primary_light: str = "#5aa0e9"
    
    # Background
    bg_primary: str = "#ffffff"
    bg_secondary: str = "#f5f5f5"
    bg_tertiary: str = "#e8e8e8"
    
    # Text
    text_primary: str = "#1a1a1a"
    text_secondary: str = "#666666"
    text_tertiary: str = "#999999"
    
    # Surface
    surface: str = "#ffffff"
    surface_variant: str = "#f0f0f0"
    
    # Border
    border: str = "#e0e0e0"
    border_strong: str = "#cccccc"
    
    # Status
    success: str = "#4caf50"
    warning: str = "#ff9800"
    error: str = "#f44336"
    info: str = "#2196f3"


# Dark theme colors
DARK_THEME = ThemeColors(
    primary="#5aa0e9",
    primary_dark="#4a90d9",
    primary_light="#6ab0f9",
    bg_primary="#1a1a2e",
    bg_secondary="#252540",
    bg_tertiary="#303050",
    text_primary="#f0f0f0",
    text_secondary="#b0b0b0",
    text_tertiary="#808080",
    surface="#252540",
    surface_variant="#303050",
    border="#404060",
    border_strong="#505070",
)

# Light theme colors
LIGHT_THEME = ThemeColors()


class ThemeManager:
    """Manages dark/light theme with auto-switch."""

    def __init__(self):
        self._current_theme: str = "light"
        self._user_preference: Optional[str] = None
        self._system_preference: str = "light"
        self._auto_switch: bool = True
        self._custom_themes: Dict[str, ThemeColors] = {}

    def set_user_preference(self, theme: str):
        """Set user theme preference."""
        if theme not in ["light", "dark", "auto"]:
            raise ValueError(f"Invalid theme: {theme}")
        
        self._user_preference = theme
        self._update_current_theme()
        logger.info(f"User theme preference set: {theme}")

    def set_system_preference(self, theme: str):
        """Set system theme preference (from OS)."""
        self._system_preference = theme
        if self._auto_switch and self._user_preference == "auto":
            self._update_current_theme()

    def enable_auto_switch(self, enabled: bool):
        """Enable/disable automatic theme switching."""
        self._auto_switch = enabled
        if enabled:
            self._update_current_theme()

    def _update_current_theme(self):
        """Update current theme based on preferences."""
        if self._user_preference == "auto":
            self._current_theme = self._system_preference
        elif self._user_preference in ["light", "dark"]:
            self._current_theme = self._user_preference
        else:
            self._current_theme = "light"

    def get_current_theme(self) -> ThemeColors:
        """Get current theme colors."""
        if self._current_theme == "dark":
            return DARK_THEME
        return LIGHT_THEME

    def get_theme_css(self) -> str:
        """Generate CSS custom properties for current theme."""
        theme = self.get_current_theme()
        
        return f'''
:root {{
  /* Primary Colors */
  --color-primary: {theme.primary};
  --color-primary-dark: {theme.primary_dark};
  --color-primary-light: {theme.primary_light};
  
  /* Background Colors */
  --color-bg-primary: {theme.bg_primary};
  --color-bg-secondary: {theme.bg_secondary};
  --color-bg-tertiary: {theme.bg_tertiary};
  
  /* Text Colors */
  --color-text-primary: {theme.text_primary};
  --color-text-secondary: {theme.text_secondary};
  --color-text-tertiary: {theme.text_tertiary};
  
  /* Surface Colors */
  --color-surface: {theme.surface};
  --color-surface-variant: {theme.surface_variant};
  
  /* Border Colors */
  --color-border: {theme.border};
  --color-border-strong: {theme.border_strong};
  
  /* Status Colors */
  --color-success: {theme.success};
  --color-warning: {theme.warning};
  --color-error: {theme.error};
  --color-info: {theme.info};
}}

/* Theme Transition */
* {{
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}}
'''

    def register_custom_theme(self, name: str, colors: ThemeColors):
        """Register a custom theme."""
        self._custom_themes[name] = colors
        logger.info(f"Registered custom theme: {name}")

    def get_theme_config(self) -> Dict[str, Any]:
        """Get theme configuration."""
        return {
            "current_theme": self._current_theme,
            "user_preference": self._user_preference,
            "system_preference": self._system_preference,
            "auto_switch_enabled": self._auto_switch,
            "custom_themes": list(self._custom_themes.keys()),
        }

    def get_toggle_js(self) -> str:
        """Generate theme toggle JavaScript."""
        return '''
// Theme Toggle
class ThemeToggle {
  constructor() {
    this.currentTheme = localStorage.getItem('theme') || 'auto';
    this.init();
  }

  init() {
    this.applyTheme(this.currentTheme);
    this.setupMediaQuery();
  }

  setupMediaQuery() {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', (e) => {
      if (this.currentTheme === 'auto') {
        this.applyTheme(e.matches ? 'dark' : 'light');
      }
    });
  }

  toggle() {
    const themes = ['light', 'dark', 'auto'];
    const currentIndex = themes.indexOf(this.currentTheme);
    this.currentTheme = themes[(currentIndex + 1) % themes.length];
    this.applyTheme(this.currentTheme);
    localStorage.setItem('theme', this.currentTheme);
  }

  applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    
    if (theme === 'auto') {
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    }
  }
}

const themeToggle = new ThemeToggle();
'''

    def get_stats(self) -> Dict[str, Any]:
        """Get theme manager statistics."""
        return {
            "current_theme": self._current_theme,
            "user_preference": self._user_preference,
            "auto_switch_enabled": self._auto_switch,
            "custom_themes_count": len(self._custom_themes),
        }


# Global default theme manager
default_theme_manager: Optional[ThemeManager] = None


def init_theme_manager() -> ThemeManager:
    """Initialize global theme manager."""
    global default_theme_manager
    default_theme_manager = ThemeManager()
    return default_theme_manager
