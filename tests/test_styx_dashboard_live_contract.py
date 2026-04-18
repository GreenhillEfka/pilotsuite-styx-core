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


def test_main_styx_route_injects_auth_token_into_template():
    content = MAIN_APP.read_text(encoding="utf-8")

    assert 'return render_template(' in content
    assert '"styx_dashboard.html",' in content
    assert 'auth_token=get_auth_token() or "",' in content
