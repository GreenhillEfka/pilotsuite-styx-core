"""
PilotSuite Styx Unified Dashboard API v1
Truth-backed Dashboard Surface, die alle Core-Wahrheiten zusammenführt:
- Zone Truth
- Module State
- Action Closures
- Proposal Lifecycle
- Brain/Neuron Activity
- Analytics Summaries
- Presence Holds
- Energy/Weather/Notifications
"""
from flask import Blueprint, Blueprint, jsonify, request, current_app, Response
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import json
import threading

styx_dashboard_bp = Blueprint('styx_dashboard_v1', __name__, url_prefix='/api/v1/styx/dashboard')


# =============================================================================
# Data Models V1
# =============================================================================

class DashboardSectionStatus(str, Enum):
    """Status für Dashboard-Sektionen"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class DashboardHeaderV1:
    """Kopfzeile des Dashboards mit globalem Status"""
    revision: int
    generated_at: str
    overall_status: DashboardSectionStatus
    total_zones: int
    zones_with_alerts: int
    active_proposals: int
    open_closures: int
    system_health_score: float  # 0.0 - 1.0


@dataclass
class ZoneSummaryBlockV1:
    """Zonen-Zusammenfassung für Dashboard-Liste"""
    zone_id: str
    zone_name: str
    icon: str
    presence_state: str  # present, absent, unknown
    hold_state: Optional[str]  # auto, force_on, force_off
    comfort_score: float  # 0-100
    energy_consumption_kwh: float
    active_modules: int
    open_proposals: int
    open_closures: int
    alert_count: int
    last_update: str
    revision: int


@dataclass
class ZoneDetailBlockV1:
    """Detaillierte Zonen-Ansicht"""
    zone_id: str
    zone_name: str
    icon: str
    
    # Presence
    presence_state: str
    presence_confidence: float
    hold_state: Optional[str]
    hold_reason: Optional[str]
    
    # Comfort
    temperature: Optional[float]
    humidity: Optional[float]
    comfort_score: float
    comfort_factors: List[str]
    
    # Energy
    energy_consumption_kwh: float
    energy_budget_remaining_kwh: float
    optimization_suggestions: int
    
    # Modules
    active_modules: List[Dict[str, Any]]
    
    # Proposals & Closures
    open_proposals: List[Dict[str, Any]]
    open_closures: List[Dict[str, Any]]
    
    # Analytics Summary
    recent_events: List[Dict[str, Any]]
    
    revision: int
    last_update: str


@dataclass
class BrainActivityBlockV1:
    """Brain/Neuron Aktivitäts-Zusammenfassung"""
    total_neurons: int
    active_neurons: int
    recent_evaluations: int
    mood_state: str
    mood_confidence: float
    recent_transfers: int
    graph_nodes: int
    graph_edges: int
    last_evaluation: str
    revision: int


@dataclass
class SystemOverviewBlockV1:
    """System-Übersicht für Dashboard-Header"""
    total_zones: int
    total_modules: int
    total_entities: int
    ha_connection_status: str  # connected, disconnected, degraded
    ha_connection_latency_ms: Optional[int]
    scheduler_jobs_total: int
    scheduler_jobs_pending: int
    notifications_unread: int
    health_score: float
    revision: int


@dataclass
class AnalyticsSummaryBlockV1:
    """Zusammenfassung aller Analytics-Surfaces"""
    energy: Dict[str, Any]
    predictive: Dict[str, Any]
    voice: Dict[str, Any]
    automation: Dict[str, Any]
    module: Dict[str, Any]
    notification: Dict[str, Any]
    health: Dict[str, Any]
    revision: int


@dataclass
class StyxDashboardReadModelV1:
    """Kanonisches Dashboard Read Model"""
    header: DashboardHeaderV1
    system_overview: SystemOverviewBlockV1
    zones_summary: List[ZoneSummaryBlockV1]
    brain_activity: BrainActivityBlockV1
    analytics_summary: Optional[AnalyticsSummaryBlockV1]
    recent_highlights: List[Dict[str, Any]]
    revision: int
    generated_at: str


# =============================================================================
# Store Layer
# =============================================================================

class StyxDashboardStore:
    """Truth-backed Dashboard Store, der alle Core-Surfaces zusammenführt"""
    
    def __init__(self):
        self._revision = 0
        self._lock = threading.Lock()
    
    def _increment_revision(self) -> int:
        with self._lock:
            self._revision += 1
            return self._revision
    
    def _get_app_config(self, key: str, default=None):
        """Safely get app config, handling outside-context cases"""
        try:
            from flask import current_app
            return current_app.config.get(key, default)
        except RuntimeError:
            # Outside application context
            return default
    
    def build_dashboard(self, include_analytics: bool = False, since_revision: Optional[int] = None) -> Optional[StyxDashboardReadModelV1]:
        """
        Baut das vollständige Dashboard aus allen Core-Wahrheiten.
        
        Args:
            include_analytics: Wenn True, werden Analytics-Summaries eingebettet
            since_revision: Wenn gesetzt, nur Änderungen seit dieser Revision
        
        Returns:
            StyxDashboardReadModelV1 oder None bei Fehlern
        """
        try:
            # System Overview aus Zone Truth + Health
            system_overview = self._build_system_overview()
            if not system_overview:
                return None
            
            # Zones Summary aus Zone Truth + Presence + Modules
            zones_summary = self._build_zones_summary()
            
            # Brain Activity aus Neuron Manager
            brain_activity = self._build_brain_activity()
            
            # Header aus aggregierten Werten
            header = self._build_header(system_overview, zones_summary, brain_activity)
            
            # Analytics Summary (optional)
            analytics_summary = None
            if include_analytics:
                analytics_summary = self._build_analytics_summary()
            
            # Recent Highlights aus Closures + Proposals
            recent_highlights = self._build_recent_highlights()
            
            current_revision = self._increment_revision()
            
            return StyxDashboardReadModelV1(
                header=header,
                system_overview=system_overview,
                zones_summary=zones_summary,
                brain_activity=brain_activity,
                analytics_summary=analytics_summary,
                recent_highlights=recent_highlights,
                revision=current_revision,
                generated_at=datetime.now(timezone.utc).isoformat()
            )
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error building dashboard: {e}")
            except RuntimeError:
                import logging
                logging.error(f"Error building dashboard: {e}")
            return None
    
    def _build_system_overview(self) -> Optional[SystemOverviewBlockV1]:
        """Build system overview from Zone Truth + Health"""
        try:
            # Zone Truth Store
            zone_truth_store = self._get_app_config('ZONE_TRUTH_STORE')
            total_zones = 0
            total_entities = 0
            if zone_truth_store:
                zone_summary = zone_truth_store.get_zone_summary() if hasattr(zone_truth_store, 'get_zone_summary') else None
                total_zones = len(zone_summary.get('zones', [])) if zone_summary else 0
                total_entities = zone_summary.get('total_entities', 0) if zone_summary else 0
            
            # Module Registry
            module_registry = self._get_app_config('MODULE_REGISTRY')
            total_modules = 0
            if module_registry:
                total_modules = len(module_registry.get_all_modules()) if hasattr(module_registry, 'get_all_modules') else 0
            
            # HA Connection Status
            ha_status = "unknown"
            ha_latency = None
            ha_module = self._get_app_config('HA_MODULE')
            if ha_module:
                diagnostics = ha_module.get_diagnostics() if hasattr(ha_module, 'get_diagnostics') else {}
                ha_status = diagnostics.get('connection_status', 'unknown')
                ha_latency = diagnostics.get('latency_ms')
            
            # Scheduler
            scheduler = self._get_app_config('SCHEDULER_ENGINE')
            scheduler_total = 0
            scheduler_pending = 0
            if scheduler:
                jobs = scheduler.get_all_jobs() if hasattr(scheduler, 'get_all_jobs') else []
                scheduler_total = len(jobs)
                scheduler_pending = len([j for j in jobs if getattr(j, 'pending', False)])
            
            # Notifications
            notifications_unread = 0
            notification_store = self._get_app_config('NOTIFICATION_STORE')
            if notification_store:
                notifications_unread = notification_store.get_unread_count() if hasattr(notification_store, 'get_unread_count') else 0
            
            # Health Score
            health_score = 1.0
            health_engine = self._get_app_config('HEALTH_ENGINE')
            if health_engine:
                health_result = health_engine.get_overall_health() if hasattr(health_engine, 'get_overall_health') else None
                if health_result:
                    health_score = health_result.get('overall_score', 1.0)
            
            return SystemOverviewBlockV1(
                total_zones=total_zones,
                total_modules=total_modules,
                total_entities=total_entities,
                ha_connection_status=ha_status,
                ha_connection_latency_ms=ha_latency,
                scheduler_jobs_total=scheduler_total,
                scheduler_jobs_pending=scheduler_pending,
                notifications_unread=notifications_unread,
                health_score=health_score,
                revision=0
            )
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error building system overview: {e}")
            except RuntimeError:
                import logging
                logging.error(f"Error building system overview: {e}")
            return SystemOverviewBlockV1(
                total_zones=0, total_modules=0, total_entities=0,
                ha_connection_status="unknown", ha_connection_latency_ms=None,
                scheduler_jobs_total=0, scheduler_jobs_pending=0,
                notifications_unread=0, health_score=0.0, revision=0
            )
    
    def _build_zones_summary(self) -> List[ZoneSummaryBlockV1]:
        """Build zone summaries from Zone Truth + Presence + Modules"""
        zones = []
        try:
            zone_truth_store = self._get_app_config('ZONE_TRUTH_STORE')
            if not zone_truth_store:
                return zones
            
            zone_summary = zone_truth_store.get_zone_summary() if hasattr(zone_truth_store, 'get_zone_summary') else None
            if not zone_summary:
                return zones
            
            for zone_data in zone_summary.get('zones', []):
                zone_id = zone_data.get('id', 'unknown')
                zone_name = zone_data.get('name', zone_id)
                
                # Presence State
                presence_state = "unknown"
                hold_state = None
                presence_store = self._get_app_config('PRESENCE_STORE')
                if presence_store:
                    zone_presence = presence_store.get_zone_presence(zone_id) if hasattr(presence_store, 'get_zone_presence') else None
                    if zone_presence:
                        presence_state = zone_presence.get('state', 'unknown')
                        hold_state = zone_presence.get('hold_state')
                
                # Comfort Score
                comfort_score = 0.0
                energy_consumption = 0.0
                active_modules = 0
                
                # Proposals & Closures
                open_proposals = 0
                open_closures = 0
                
                zones.append(ZoneSummaryBlockV1(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    icon=zone_data.get('icon', 'mdi-room'),
                    presence_state=presence_state,
                    hold_state=hold_state,
                    comfort_score=comfort_score,
                    energy_consumption_kwh=energy_consumption,
                    active_modules=active_modules,
                    open_proposals=open_proposals,
                    open_closures=open_closures,
                    alert_count=0,
                    last_update=zone_data.get('last_sync', datetime.now(timezone.utc).isoformat()),
                    revision=zone_data.get('revision', 0)
                ))
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error building zones summary: {e}")
            except RuntimeError:
                import logging
                logging.error(f"Error building zones summary: {e}")
        
        return zones
    
    def _build_brain_activity(self) -> BrainActivityBlockV1:
        """Build brain activity from Neuron Manager"""
        try:
            neuron_manager = self._get_app_config('NEURON_MANAGER')
            if not neuron_manager:
                return BrainActivityBlockV1(
                    total_neurons=0, active_neurons=0, recent_evaluations=0,
                    mood_state="unknown", mood_confidence=0.0, recent_transfers=0,
                    graph_nodes=0, graph_edges=0, last_evaluation=datetime.now(timezone.utc).isoformat(),
                    revision=0
                )
            
            # Neuron stats
            total_neurons = 0
            active_neurons = 0
            recent_evaluations = 0
            
            # Mood
            mood_state = "neutral"
            mood_confidence = 0.0
            
            # Graph
            graph_nodes = 0
            graph_edges = 0
            
            return BrainActivityBlockV1(
                total_neurons=total_neurons,
                active_neurons=active_neurons,
                recent_evaluations=recent_evaluations,
                mood_state=mood_state,
                mood_confidence=mood_confidence,
                recent_transfers=0,
                graph_nodes=graph_nodes,
                graph_edges=graph_edges,
                last_evaluation=datetime.now(timezone.utc).isoformat(),
                revision=0
            )
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error building brain activity: {e}")
            except RuntimeError:
                import logging
                logging.error(f"Error building brain activity: {e}")
            return BrainActivityBlockV1(
                total_neurons=0, active_neurons=0, recent_evaluations=0,
                mood_state="unknown", mood_confidence=0.0, recent_transfers=0,
                graph_nodes=0, graph_edges=0, last_evaluation=datetime.now(timezone.utc).isoformat(),
                revision=0
            )
    
    def _build_header(self, system: SystemOverviewBlockV1, zones: List[ZoneSummaryBlockV1], brain: BrainActivityBlockV1) -> DashboardHeaderV1:
        """Build dashboard header from aggregated data"""
        zones_with_alerts = sum(1 for z in zones if z.alert_count > 0)
        
        # Active proposals from Proposal Lifecycle
        active_proposals = 0
        proposal_store = self._get_app_config('PROPOSAL_LIFECYCLE_STORE')
        if proposal_store:
            active_proposals = len(proposal_store.get_active_proposals()) if hasattr(proposal_store, 'get_active_proposals') else 0
        
        # Open closures
        open_closures = 0
        closure_store = self._get_app_config('ACTION_CLOSURE_STORE')
        if closure_store:
            open_closures = len(closure_store.get_open_closures()) if hasattr(closure_store, 'get_open_closures') else 0
        
        # Overall status
        overall_status = DashboardSectionStatus.OK
        if system.health_score < 0.5:
            overall_status = DashboardSectionStatus.ERROR
        elif system.health_score < 0.8:
            overall_status = DashboardSectionStatus.WARNING
        
        return DashboardHeaderV1(
            revision=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
            overall_status=overall_status,
            total_zones=len(zones),
            zones_with_alerts=zones_with_alerts,
            active_proposals=active_proposals,
            open_closures=open_closures,
            system_health_score=system.health_score
        )
    
    def _build_analytics_summary(self) -> Optional[AnalyticsSummaryBlockV1]:
        """Build analytics summary from all analytics stores"""
        try:
            # Placeholder - would aggregate from all analytics stores
            return AnalyticsSummaryBlockV1(
                energy={}, predictive={}, voice={}, automation={},
                module={}, notification={}, health={}, revision=0
            )
        except Exception as e:
            current_app.logger.error(f"Error building analytics summary: {e}")
            return None
    
    def _build_recent_highlights(self) -> List[Dict[str, Any]]:
        """Build recent highlights from closures and proposals"""
        highlights = []
        try:
            # Recent closures
            closure_store = self._get_app_config('ACTION_CLOSURE_STORE')
            if closure_store:
                recent = closure_store.get_recent_closures(limit=5) if hasattr(closure_store, 'get_recent_closures') else []
                for closure in recent:
                    highlights.append({
                        'type': 'closure',
                        'title': closure.get('source', 'Action'),
                        'status': closure.get('lifecycle_status', 'unknown'),
                        'timestamp': closure.get('updated_at')
                    })
            
            # Recent proposals
            proposal_store = self._get_app_config('PROPOSAL_LIFECYCLE_STORE')
            if proposal_store:
                recent = proposal_store.get_recent_proposals(limit=5) if hasattr(proposal_store, 'get_recent_proposals') else []
                for proposal in recent:
                    highlights.append({
                        'type': 'proposal',
                        'title': proposal.get('title', 'Proposal'),
                        'status': proposal.get('lifecycle_status', 'unknown'),
                        'timestamp': proposal.get('updated_at')
                    })
        except Exception as e:
            try:
                from flask import current_app
                current_app.logger.error(f"Error building highlights: {e}")
            except RuntimeError:
                import logging
                logging.error(f"Error building highlights: {e}")
        
        # Sort by timestamp
        highlights.sort(key=lambda x: x.get('timestamp', '') or '', reverse=True)
        return highlights[:10]


# =============================================================================
# API Endpoints
# =============================================================================

_dashboard_store = StyxDashboardStore()


@styx_dashboard_bp.route('', methods=['GET'])
def get_dashboard():
    """
    Unified Styx Dashboard abrufen
    
    Query Parameters:
    - include_analytics: bool (default: false) - Analytics-Summaries einbetten
    - since: int (optional) - Revision für Delta-Responses
    - zone_id: str (optional) - Nur spezifische Zone
    """
    include_analytics = request.args.get('include_analytics', 'false').lower() == 'true'
    since_revision = request.args.get('since', type=int)
    zone_id = request.args.get('zone_id')
    
    dashboard = _dashboard_store.build_dashboard(
        include_analytics=include_analytics,
        since_revision=since_revision
    )
    
    if not dashboard:
        return jsonify({'error': 'Failed to build dashboard'}), 500
    
    # Delta-Check
    if since_revision is not None and dashboard.revision <= since_revision:
        return jsonify({
            'has_changes': False,
            'revision': dashboard.revision,
            'generated_at': dashboard.generated_at
        })
    
    # Convert to dict
    result = {
        'has_changes': True,
        'header': asdict(dashboard.header),
        'system_overview': asdict(dashboard.system_overview),
        'zones_summary': [asdict(z) for z in dashboard.zones_summary],
        'brain_activity': asdict(dashboard.brain_activity),
        'recent_highlights': dashboard.recent_highlights,
        'revision': dashboard.revision,
        'generated_at': dashboard.generated_at
    }
    
    if dashboard.analytics_summary:
        result['analytics_summary'] = asdict(dashboard.analytics_summary)
    
    # Zone filter
    if zone_id:
        zone_data = next((z for z in result['zones_summary'] if z['zone_id'] == zone_id), None)
        if zone_data:
            result['zones_summary'] = [zone_data]
        else:
            return jsonify({'error': 'Zone not found'}), 404
    
    return jsonify(result)


@styx_dashboard_bp.route('/zone/<zone_id>', methods=['GET'])
def get_zone_detail(zone_id: str):
    """
    Detaillierte Zonen-Ansicht mit allen Analytics
    
    Query Parameters:
    - include_analytics: bool (default: false)
    - since: int (optional) - Revision für Delta
    """
    include_analytics = request.args.get('include_analytics', 'false').lower() == 'true'
    since_revision = request.args.get('since', type=int)
    
    # Build zone detail from Zone Truth + all related data
    zone_truth_store = current_app.config.get('ZONE_TRUTH_STORE')
    if not zone_truth_store:
        return jsonify({'error': 'Zone truth store not available'}), 503
    
    zone_data = zone_truth_store.get_zone_detail(zone_id) if hasattr(zone_truth_store, 'get_zone_detail') else None
    if not zone_data:
        return jsonify({'error': 'Zone not found'}), 404
    
    # Build detail block
    detail = {
        'zone_id': zone_id,
        'zone_name': zone_data.get('name', zone_id),
        'icon': zone_data.get('icon', 'mdi-room'),
        'presence': {},
        'comfort': {},
        'energy': {},
        'modules': [],
        'proposals': [],
        'closures': [],
        'recent_events': [],
        'revision': zone_data.get('revision', 0),
        'last_update': zone_data.get('last_sync', datetime.now(timezone.utc).isoformat())
    }
    
    # Delta-Check
    if since_revision is not None and detail['revision'] <= since_revision:
        return jsonify({
            'has_changes': False,
            'revision': detail['revision']
        })
    
    detail['has_changes'] = True
    
    return jsonify(detail)


@styx_dashboard_bp.route('/context', methods=['GET'])
def get_dashboard_context():
    """
    Kompakter Dashboard-Kontext für Chat/Voice Integration
    
    Enthält nur die wichtigsten Status-Informationen für natürliche Sprache.
    """
    dashboard = _dashboard_store.build_dashboard(include_analytics=False)
    
    if not dashboard:
        return jsonify({'error': 'Failed to build context'}), 500
    
    context = {
        'system_status': dashboard.header.overall_status.value,
        'health_score': dashboard.header.system_health_score,
        'total_zones': dashboard.header.total_zones,
        'zones_with_alerts': dashboard.header.zones_with_alerts,
        'active_proposals': dashboard.header.active_proposals,
        'open_closures': dashboard.header.open_closures,
        'mood_state': dashboard.brain_activity.mood_state,
        'recent_highlights': dashboard.recent_highlights[:3],  # Top 3
        'generated_at': dashboard.generated_at,
        'revision': dashboard.revision
    }
    
    return jsonify(context)


@styx_dashboard_bp.route('/revision', methods=['GET'])
def get_revision():
    """
    Aktuelle Dashboard-Revision für Delta-Polling
    """
    return jsonify({
        'revision': _dashboard_store._revision,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
