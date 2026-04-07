"""PilotSuite Additional Lovelace Cards — Extended Card Library."""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# CARD 6: PLUGIN MANAGER CARD
# =============================================================================

@dataclass
class PluginManagerCardConfig:
    """Configuration for plugin manager card."""
    title: str = "Plugin Manager"
    show_installed: bool = True
    show_available: bool = True
    allow_install: bool = True


class PluginManagerCard:
    """
    Lovelace Card: Plugin Manager
    
    Features:
    - Browse available plugins
    - Install/uninstall plugins
    - View plugin details
    - Update plugins
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-plugin-manager
    title: Plugin Manager
    show_installed: true
    show_available: true
    ```
    """

    def __init__(self, config: PluginManagerCardConfig):
        self.config = config
        self._installed_plugins = []
        self._available_plugins = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-plugin-manager",
            "title": self.config.title,
            "installed_plugins": self._installed_plugins if self.config.show_installed else [],
            "available_plugins": self._available_plugins if self.config.show_available else [],
            "actions": [
                {"label": "Refresh", "action": "refresh"},
                {"label": "Browse Hub", "action": "browse_hub"},
            ]
        }


# =============================================================================
# CARD 7: SYNC STATUS CARD
# =============================================================================

@dataclass
class SyncStatusCardConfig:
    """Configuration for sync status card."""
    title: str = "Multi-Home Sync"
    show_remote_homes: bool = True
    show_sync_history: bool = True


class SyncStatusCard:
    """
    Lovelace Card: Multi-Home Sync Status
    
    Features:
    - View remote homes
    - Sync status indicator
    - Last sync time
    - Manual sync trigger
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-sync-status
    title: Multi-Home Sync
    show_remote_homes: true
    show_sync_history: true
    ```
    """

    def __init__(self, config: SyncStatusCardConfig):
        self.config = config
        self._remote_homes = []
        self._sync_status = "idle"

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-sync-status",
            "title": self.config.title,
            "sync_status": self._sync_status,
            "remote_homes": self._remote_homes if self.config.show_remote_homes else [],
            "actions": [
                {"label": "Sync Now", "action": "sync_now"},
                {"label": "Configure", "action": "configure"},
            ]
        }


# =============================================================================
# CARD 8: REPORT VIEWER CARD
# =============================================================================

@dataclass
class ReportViewerCardConfig:
    """Configuration for report viewer card."""
    title: str = "Reports"
    report_type: str = "daily"  # daily, weekly, energy, automation
    show_charts: bool = True


class ReportViewerCard:
    """
    Lovelace Card: Report Viewer
    
    Features:
    - View daily/weekly reports
    - Energy reports
    - Automation performance
    - Export reports
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-report-viewer
    title: Reports
    report_type: daily
    show_charts: true
    ```
    """

    def __init__(self, config: ReportViewerCardConfig):
        self.config = config
        self._reports = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-report-viewer",
            "title": self.config.title,
            "report_type": self.config.report_type,
            "reports": self._reports,
            "show_charts": self.config.show_charts,
            "actions": [
                {"label": "Refresh", "action": "refresh"},
                {"label": "Export", "action": "export"},
            ]
        }


# =============================================================================
# CARD 9: CONTRACT STATUS CARD
# =============================================================================

@dataclass
class ContractStatusCardConfig:
    """Configuration for contract status card."""
    title: str = "Contract Status"
    show_drift: bool = True


class ContractStatusCard:
    """
    Lovelace Card: Contract Status
    
    Features:
    - View contract status
    - Drift detection alerts
    - Schema validation status
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-contract-status
    title: Contract Status
    show_drift: true
    ```
    """

    def __init__(self, config: ContractStatusCardConfig):
        self.config = config
        self._contracts = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        drift_detected = any(c.get("drift") for c in self._contracts)
        
        return {
            "type": "custom:pilotsuite-contract-status",
            "title": self.config.title,
            "contracts": self._contracts,
            "drift_detected": drift_detected if self.config.show_drift else False,
            "actions": [
                {"label": "Validate All", "action": "validate"},
                {"label": "Fix Drift", "action": "fix_drift"},
            ]
        }


# =============================================================================
# CARD 10: ML MODEL STATUS CARD
# =============================================================================

@dataclass
class MLModelStatusCardConfig:
    """Configuration for ML model status card."""
    title: str = "ML Models"
    show_performance: bool = True


class MLModelStatusCard:
    """
    Lovelace Card: ML Model Status
    
    Features:
    - View model status
    - Training progress
    - Performance metrics
    - Retraining trigger
    
    YAML Config:
    ```yaml
    type: custom:pilotsuite-ml-status
    title: ML Models
    show_performance: true
    ```
    """

    def __init__(self, config: MLModelStatusCardConfig):
        self.config = config
        self._models = []

    def render(self) -> Dict[str, Any]:
        """Render card HTML."""
        return {
            "type": "custom:pilotsuite-ml-status",
            "title": self.config.title,
            "models": self._models,
            "show_performance": self.config.show_performance,
            "actions": [
                {"label": "Retrain All", "action": "retrain"},
                {"label": "View Metrics", "action": "metrics"},
            ]
        }


# =============================================================================
# CARD REGISTRY (EXTENDED)
# =============================================================================

ADDITIONAL_CARDS = {
    "pilotsuite-plugin-manager": PluginManagerCard,
    "pilotsuite-sync-status": SyncStatusCard,
    "pilotsuite-report-viewer": ReportViewerCard,
    "pilotsuite-contract-status": ContractStatusCard,
    "pilotsuite-ml-status": MLModelStatusCard,
}

# Total cards now: 14 (original) + 5 (additional) = 19 cards!
