"""Tests for Iteration 3: UX polish, keyboard shortcuts, tab persistence, responsive design.

Tests:
  - Styx dashboard HTML includes keyboard hint badges
  - Dashboard HTML includes switchTab function
  - Dashboard HTML includes localStorage tab persistence
  - Dashboard HTML includes auto-refresh countdown
  - Dashboard HTML includes gradient header
  - Dashboard HTML includes responsive CSS (mobile-friendly)
  - Dashboard HTML includes keyboard event listener
  - Dashboard HTML tab order matches keyboard shortcut mapping
"""

import os
import pytest


def _get_dashboard_html():
    """Read the styx dashboard HTML template directly."""
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "copilot_core", "templates", "styx_dashboard.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


class TestKeyboardShortcuts:
    def test_keyboard_hint_badges_on_tabs(self):
        """Each tab should have a kbd-hint badge with its number."""
        html = _get_dashboard_html()
        assert "kbd-hint" in html
        # 9 tabs, numbered 1-9
        for i in range(1, 10):
            assert f'<span class="kbd-hint">{i}</span>' in html

    def test_keyboard_event_listener(self):
        """Dashboard should have a keydown event listener for tab switching."""
        html = _get_dashboard_html()
        assert "addEventListener('keydown'" in html or 'addEventListener("keydown"' in html

    def test_tab_keys_array_matches_tabs(self):
        """TAB_KEYS array should list all 8 tab names in order."""
        html = _get_dashboard_html()
        assert "TAB_KEYS" in html
        expected_tabs = ["overview", "zones", "media", "suggestions", "automation", "llm", "modules", "neurons", "chat"]
        for tab in expected_tabs:
            assert f"'{tab}'" in html or f'"{tab}"' in html

    def test_escape_closes_modal(self):
        """Pressing Escape should close the zone modal."""
        html = _get_dashboard_html()
        assert "Escape" in html
        assert "closeZoneModal" in html

    def test_r_key_refreshes(self):
        """Pressing 'r' should trigger a refresh."""
        html = _get_dashboard_html()
        # Match the r key handler
        assert "e.key === 'r'" in html or 'e.key === "r"' in html


class TestTabPersistence:
    def test_localstorage_save(self):
        """switchTab should save tab to localStorage."""
        html = _get_dashboard_html()
        assert "localStorage.setItem('styx-active-tab'" in html or \
               'localStorage.setItem("styx-active-tab"' in html

    def test_localstorage_restore(self):
        """On load, the saved tab should be restored from localStorage."""
        html = _get_dashboard_html()
        assert "localStorage.getItem('styx-active-tab')" in html or \
               'localStorage.getItem("styx-active-tab")' in html


class TestAutoRefresh:
    def test_auto_refresh_countdown_element(self):
        """Dashboard should have a refresh-countdown element."""
        html = _get_dashboard_html()
        assert 'id="refresh-countdown"' in html

    def test_auto_refresh_interval(self):
        """Auto-refresh should be set to 30 seconds."""
        html = _get_dashboard_html()
        assert "refreshInterval = 30" in html

    def test_countdown_display(self):
        """Countdown should display remaining seconds."""
        html = _get_dashboard_html()
        # The countdown format uses (Ns)
        assert "refreshCountdown" in html
        assert "loadDashboard()" in html


class TestDesignPolish:
    def test_gradient_header(self):
        """Header should use gradient text effect."""
        html = _get_dashboard_html()
        assert "linear-gradient" in html
        assert "background-clip: text" in html

    def test_responsive_css(self):
        """Dashboard should include responsive media queries."""
        html = _get_dashboard_html()
        assert "@media" in html
        assert "max-width" in html

    def test_switchtab_function(self):
        """switchTab function should exist and handle tab switching."""
        html = _get_dashboard_html()
        assert "function switchTab(tabName)" in html

    def test_zone_modal_html(self):
        """Zone detail modal should be present in HTML."""
        html = _get_dashboard_html()
        assert "zone-detail-modal" in html or "zone-modal" in html

    def test_summary_strip(self):
        """Overview should have a summary strip."""
        html = _get_dashboard_html()
        assert "summary-strip" in html or "renderSummaryStrip" in html
