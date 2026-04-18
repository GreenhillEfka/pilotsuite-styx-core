from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "addons" / "pilotsuite" / "app" / "copilot_core" / "templates" / "styx_dashboard.html"
MAIN_APP = ROOT / "addons" / "pilotsuite" / "app" / "main.py"


def test_styx_dashboard_template_loads_socketio_client_and_token_fallback():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert '<script src="/socket.io/socket.io.js"></script>' in content
    assert "const INJECTED_TOKEN = {{ (auth_token|default('', true))|tojson }};" in content
    assert "sessionStorage.getItem('styx-auth-token')" in content
    assert "sessionStorage.setItem('styx-auth-token', TOKEN);" in content


def test_styx_dashboard_template_wires_live_updates_for_mood_and_neurons():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "function connectLiveUpdates()" in content
    assert "liveSocket.emit('join_room', { room: 'neurons' });" in content
    assert "liveSocket.on('mood_update', applyMoodRealtime);" in content
    assert "liveSocket.on('neuron_fire', evt => applyNeuronRealtime(evt, { firing: true }));" in content
    assert "liveSocket.on('neuron_state_change', evt => applyNeuronRealtime(evt));" in content
    assert "connectLiveUpdates();" in content


def test_styx_dashboard_template_uses_graph_update_delta_for_canvas_highlights():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert "let brainData = { nodes: 0, edges: 0, totalEvents: 0 }, neuronsData = {}, liveSocket = null, graphDeltaState = null, brainDeltaAnimationId = null;" in content
    assert "let graphTopologyState = { nodes: [], edges: [], positions: {}, fetchedAt: 0 }, graphTopologyRefreshPromise = null;" in content
    assert "const GRAPH_TOPOLOGY_LIMITS = { nodes: 48, edges: 96 };" in content
    assert "function applyGraphRealtime(evt)" in content
    assert "function deriveGraphDeltaHighlight(payload)" in content
    assert "async function refreshGraphTopology(force = false)" in content
    assert "function computeGraphTopologyPositions(nodes = [], edges = [])" in content
    assert "function getGraphAnchorPoint(nodeId, fallbackKey, cx, cy, minRadius, maxRadius, W, H)" in content
    assert "drawGraphTopologyBackdrop(ctx, W, H);" in content
    assert "fetchJSON(`/api/v1/graph/state?limitNodes=${GRAPH_TOPOLOGY_LIMITS.nodes}&limitEdges=${GRAPH_TOPOLOGY_LIMITS.edges}`)" in content
    assert "function drawGraphDeltaOverlay(ctx, W, H, cx, cy)" in content
    assert "drawGraphDeltaOverlay(ctx, W, H, cx, cy);" in content
    assert "liveSocket.on('graph_update', applyGraphRealtime);" in content
    assert "if (graphDeltaState) ensureBrainDeltaAnimation();" in content
    assert "highlightedNodes" not in content
    assert "highlightedEdges" not in content


def test_main_styx_route_injects_auth_token_into_template():
    content = MAIN_APP.read_text(encoding="utf-8")

    assert 'return render_template(' in content
    assert '"styx_dashboard.html",' in content
    assert 'auth_token=get_auth_token() or "",' in content
