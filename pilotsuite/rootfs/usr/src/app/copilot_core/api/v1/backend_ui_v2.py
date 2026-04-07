"""Unified SOTA Backend UI — PilotSuite Admin.
Single entry point for all symbiotic entities with tabbed navigation.
"""
from flask import Blueprint, render_template_string, jsonify

bp = Blueprint("admin_ui", __name__, url_prefix="/admin")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PilotSuite Core Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f8f9fa; font-family: 'Inter', sans-serif; }
        .sidebar { height: 100vh; background: #212529; color: white; padding: 20px; position: fixed; width: 240px; }
        .content { margin-left: 240px; padding: 40px; }
        .nav-link { color: #adb5bd; margin-bottom: 10px; border-radius: 6px; }
        .nav-link.active { background: #0d6efd; color: white; }
        .card { border: none; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .badge-status { font-size: 0.8rem; padding: 4px 8px; border-radius: 20px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>PilotSuite</h4>
        <hr>
        <nav class="nav flex-column">
            <a class="nav-link active" href="#" onclick="showTab('zones')">🏠 Habitus Zonen</a>
            <a class="nav-link" href="#" onclick="showTab('contexts')">🎭 Room Contexts</a>
            <a class="nav-link" href="#" onclick="showTab('devices')">🔗 Device Links</a>
            <a class="nav-link" href="#" onclick="showTab('presence')">👤 Presence</a>
            <a class="nav-link" href="#" onclick="showTab('intents')">🎯 Intents</a>
            <a class="nav-link" href="#" onclick="showTab('actions')">⚡ Actions</a>
            <a class="nav-link" href="#" onclick="showTab('events')">📡 Event Bus</a>
            <a class="nav-link" href="#" onclick="showTab('memory')">🧠 Learning Memory</a>
        </nav>
    </div>
    <div class="content">
        <div id="tab-content">
            <!-- Dynamic Content -->
        </div>
    </div>

    <script>
        async function fetchAPI(path) {
            const r = await fetch('/api/v1' + path);
            return await r.json();
        }

        async function showTab(tab) {
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            event.target.classList.add('active');
            
            const container = document.getElementById('tab-content');
            container.innerHTML = '<h2>Lade...</h2>';

            if (tab === 'zones') {
                const data = await fetchAPI('/habitus/zones');
                container.innerHTML = `<h1>Habitus Zonen</h1><div class="row">` + 
                    data.zones.map(z => `
                        <div class="col-md-4 mb-4">
                            <div class="card p-3">
                                <h5>${z.name}</h5>
                                <p class="text-muted">${z.zone_id}</p>
                                <div><span class="badge bg-primary">${z.active_context}</span></div>
                            </div>
                        </div>`).join('') + `</div>`;
            }
            if (tab === 'contexts') {
                const data = await fetchAPI('/contexts/rooms');
                container.innerHTML = `<h1>Room Contexts</h1><div class="row">` + 
                    data.contexts.map(c => `
                        <div class="col-md-4 mb-4">
                            <div class="card p-3">
                                <h5>${c.name}</h5>
                                <p class="text-muted">${c.context_id}</p>
                                <div><span class="badge bg-success">${c.active ? 'AKTIV' : 'INAKTIV'}</span></div>
                            </div>
                        </div>`).join('') + `</div>`;
            }
            if (tab === 'devices') {
                const data = await fetchAPI('/devices/links');
                container.innerHTML = `<h1>Device Links</h1><div class="row">` + 
                    data.links.map(d => `
                        <div class="col-md-3 mb-3">
                            <div class="card p-2">
                                <h6>${d.name}</h6>
                                <small class="text-muted">${d.domain}</small><br/>
                                <small>${d.capabilities?.length || 0} Capabilities</small>
                            </div>
                        </div>`).join('') + `</div>`;
            }
            if (tab === 'presence') {
                const data = await fetchAPI('/entities/presence');
                container.innerHTML = `<h1>Presence Entities</h1><div class="row">` + 
                    data.entities.map(e => `
                        <div class="col-md-3 mb-3">
                            <div class="card p-2">
                                <h6>${e.name}</h6>
                                <span class="badge ${e.current_state ? 'bg-success' : 'bg-secondary'}">${e.current_state ? 'PRESENT' : 'ABSENT'}</span>
                            </div>
                        </div>`).join('') + `</div>`;
            }
            if (tab === 'intents') {
                const data = await fetchAPI('/intents');
                container.innerHTML = `<h1>Intent Manager</h1><div class="row">` + 
                    data.intents.map(i => `
                        <div class="col-md-4 mb-3">
                            <div class="card p-3">
                                <h5>${i.name}</h5>
                                <small>${i.trigger_phrases?.join(', ')}</small><br/>
                                <span class="badge bg-info">${i.confidence_threshold * 100}%</span>
                            </div>
                        </div>`).join('') + `</div>`;
            }
            if (tab === 'actions') {
                const data = await fetchAPI('/actions');
                container.innerHTML = `<h1>Action Executor</h1><div class="row">` + 
                    data.actions.map(a => `
                        <div class="col-md-4 mb-3">
                            <div class="card p-3">
                                <h5>${a.name}</h5>
                                <small>Executed: ${a.execution_count || 0}x</small>
                            </div>
                        </div>`).join('') + `</div>`;
            }
            if (tab === 'events') {
                const data = await fetchAPI('/events/recent?limit=20');
                container.innerHTML = `<h1>Event Bus</h1><table class="table"><thead><tr><th>Event</th><th>Source</th><th>Time</th></tr></thead><tbody>` + 
                    data.events.map(e => `<tr><td>${e.event_type}</td><td>${e.source}</td><td>${e.timestamp}</td></tr>`).join('') + `</tbody></table>`;
            }
            if (tab === 'memory') {
                const data = await fetchAPI('/memory/patterns');
                container.innerHTML = `<h1>Learning Memory</h1><div class="row">` + 
                    data.patterns.map(p => `
                        <div class="col-md-4 mb-3">
                            <div class="card p-3">
                                <h5>${p.pattern_id}</h5>
                                <small>Freq: ${p.frequency}</small><br/>
                                <div class="progress"><div class="progress-bar" style="width:${p.confidence*100}%">${Math.round(p.confidence*100)}%</div></div>
                            </div>
                        </div>`).join('') + `</div>`;
            }
        }
        
        // Initial load
        showTab('zones');
    </script>
</body>
</html>
"""

@bp.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)
