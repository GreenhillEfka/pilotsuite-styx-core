"""Tests for Sankey Energy Flow Diagram renderer.

Covers:
- SankeyNode / SankeyFlow / SankeyData dataclasses
- SankeyRenderer SVG generation (dark/light themes)
- build_sankey_from_energy data builder
- Empty state handling
- Flow bezier curve rendering
- Node positioning and layout
"""
import sys
import os

# Add app root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copilot_core.energy.sankey import (
    SankeyNode,
    SankeyFlow,
    SankeyData,
    SankeyRenderer,
    build_sankey_from_energy,
    get_device_color,
    CATEGORY_COLORS,
    DARK_THEME,
    LIGHT_THEME,
)


# ──────────────────────────────────────────────────────────────────────────
# Tests: Dataclasses
# ──────────────────────────────────────────────────────────────────────────

class TestDataclasses:
    def test_sankey_node_defaults(self):
        node = SankeyNode(id="grid", label="Grid", value=5.0)
        assert node.id == "grid"
        assert node.label == "Grid"
        assert node.value == 5.0
        assert node.color == "#60a5fa"
        assert node.category == "device"

    def test_sankey_flow(self):
        flow = SankeyFlow(source="grid", target="washer", value=2.0)
        assert flow.source == "grid"
        assert flow.target == "washer"
        assert flow.value == 2.0
        assert flow.color is None

    def test_sankey_data(self):
        data = SankeyData(
            nodes=[SankeyNode("a", "A", 1.0)],
            flows=[SankeyFlow("a", "b", 0.5)],
            title="Test",
            unit="kWh",
        )
        assert len(data.nodes) == 1
        assert len(data.flows) == 1
        assert data.title == "Test"
        assert data.unit == "kWh"

    def test_sankey_data_defaults(self):
        data = SankeyData()
        assert data.nodes == []
        assert data.flows == []
        assert data.unit == "W"


# ──────────────────────────────────────────────────────────────────────────
# Tests: Color Helpers
# ──────────────────────────────────────────────────────────────────────────

class TestColors:
    def test_known_device_color(self):
        assert get_device_color("washer") == "#f472b6"
        assert get_device_color("dryer") == "#fb923c"
        assert get_device_color("ev_charger") == "#2dd4bf"

    def test_unknown_device_color(self):
        assert get_device_color("unknown_device") == "#94a3b8"

    def test_theme_colors_complete(self):
        for key in ["bg", "text", "text_secondary", "node_stroke", "flow_opacity", "node_opacity"]:
            assert key in DARK_THEME
            assert key in LIGHT_THEME


# ──────────────────────────────────────────────────────────────────────────
# Tests: SankeyRenderer
# ──────────────────────────────────────────────────────────────────────────

class TestRenderer:
    def test_render_empty(self):
        renderer = SankeyRenderer()
        data = SankeyData(title="Empty Test")
        svg = renderer.render(data)
        assert "<svg" in svg
        assert "Keine Energiedaten" in svg
        assert "</svg>" in svg

    def test_render_basic_flow(self):
        renderer = SankeyRenderer(width=600, height=300)
        data = SankeyData(
            nodes=[
                SankeyNode("grid", "Grid", 10.0, "#60a5fa", "source"),
                SankeyNode("washer", "Washer", 10.0, "#f472b6", "device"),
            ],
            flows=[SankeyFlow("grid", "washer", 10.0)],
            title="Test Flow",
        )
        svg = renderer.render(data)
        assert "<svg" in svg
        assert "Test Flow" in svg
        assert 'class="flow"' in svg
        assert 'class="node-rect"' in svg

    def test_render_dark_theme(self):
        renderer = SankeyRenderer(theme="dark")
        data = SankeyData(
            nodes=[
                SankeyNode("grid", "Grid", 5.0, "#60a5fa", "source"),
                SankeyNode("dev", "Device", 5.0, "#94a3b8", "device"),
            ],
            flows=[SankeyFlow("grid", "dev", 5.0)],
        )
        svg = renderer.render(data)
        assert DARK_THEME["bg"] in svg

    def test_render_light_theme(self):
        renderer = SankeyRenderer(theme="light")
        data = SankeyData(
            nodes=[
                SankeyNode("grid", "Grid", 5.0, "#60a5fa", "source"),
                SankeyNode("dev", "Device", 5.0, "#94a3b8", "device"),
            ],
            flows=[SankeyFlow("grid", "dev", 5.0)],
        )
        svg = renderer.render(data)
        assert LIGHT_THEME["bg"] in svg

    def test_render_multiple_flows(self):
        renderer = SankeyRenderer()
        data = SankeyData(
            nodes=[
                SankeyNode("grid", "Grid", 15.0, "#60a5fa", "source"),
                SankeyNode("solar", "Solar", 5.0, "#fbbf24", "source"),
                SankeyNode("washer", "Washer", 10.0, "#f472b6", "device"),
                SankeyNode("dryer", "Dryer", 10.0, "#fb923c", "device"),
            ],
            flows=[
                SankeyFlow("grid", "washer", 7.0),
                SankeyFlow("grid", "dryer", 8.0),
                SankeyFlow("solar", "washer", 3.0),
                SankeyFlow("solar", "dryer", 2.0),
            ],
        )
        svg = renderer.render(data)
        # Should have 4 flow paths
        assert svg.count('class="flow"') == 4

    def test_render_has_tooltips(self):
        renderer = SankeyRenderer()
        data = SankeyData(
            nodes=[
                SankeyNode("grid", "Grid", 5.0, "#60a5fa", "source"),
                SankeyNode("dev", "Device", 5.0, "#94a3b8", "device"),
            ],
            flows=[SankeyFlow("grid", "dev", 5.0)],
        )
        svg = renderer.render(data)
        assert "<title>" in svg

    def test_render_svg_valid_xml(self):
        renderer = SankeyRenderer()
        data = SankeyData(
            nodes=[
                SankeyNode("grid", "Grid", 5.0, "#60a5fa", "source"),
                SankeyNode("dev", "Device", 5.0, "#94a3b8", "device"),
            ],
            flows=[SankeyFlow("grid", "dev", 5.0)],
        )
        svg = renderer.render(data)
        assert svg.startswith("<svg")
        assert svg.strip().endswith("</svg>")

    def test_custom_dimensions(self):
        renderer = SankeyRenderer(width=1000, height=600)
        data = SankeyData(
            nodes=[
                SankeyNode("a", "A", 1.0, category="source"),
                SankeyNode("b", "B", 1.0, category="device"),
            ],
            flows=[SankeyFlow("a", "b", 1.0)],
        )
        svg = renderer.render(data)
        assert 'width="1000"' in svg
        assert 'height="600"' in svg


# ──────────────────────────────────────────────────────────────────────────
# Tests: build_sankey_from_energy
# ──────────────────────────────────────────────────────────────────────────

class TestBuildSankey:
    def test_basic_consumption(self):
        data = build_sankey_from_energy(
            consumption=10.0,
            production=0.0,
            baselines={"washer": 1.5, "dryer": 3.5},
        )
        assert len(data.nodes) > 0
        assert len(data.flows) > 0
        # Should have grid as source
        source_ids = [n.id for n in data.nodes if n.category == "source"]
        assert "grid" in source_ids

    def test_with_solar_production(self):
        data = build_sankey_from_energy(
            consumption=10.0,
            production=4.0,
            baselines={"washer": 1.5},
        )
        source_ids = [n.id for n in data.nodes if n.category == "source"]
        assert "grid" in source_ids
        assert "solar" in source_ids

    def test_solar_covers_all(self):
        """When production >= consumption, grid should not appear."""
        data = build_sankey_from_energy(
            consumption=5.0,
            production=8.0,
            baselines={"washer": 1.5},
        )
        source_ids = [n.id for n in data.nodes if n.category == "source"]
        assert "solar" in source_ids
        # grid_value = max(5-8, 0) = 0, so no grid
        assert "grid" not in source_ids

    def test_with_zone_data(self):
        data = build_sankey_from_energy(
            consumption=10.0,
            production=3.0,
            baselines={},
            zone_data={"Kitchen": 4.0, "Living Room": 3.0},
        )
        node_ids = [n.id for n in data.nodes]
        assert "zone_kitchen" in node_ids
        assert "zone_living_room" in node_ids

    def test_zero_consumption(self):
        """Zero consumption with some production should work."""
        data = build_sankey_from_energy(
            consumption=0.0,
            production=5.0,
            baselines={"washer": 1.5},
        )
        # Should have solar source
        source_ids = [n.id for n in data.nodes if n.category == "source"]
        assert "solar" in source_ids

    def test_custom_title(self):
        data = build_sankey_from_energy(
            consumption=5.0,
            production=0.0,
            baselines={"washer": 1.0},
            title="Custom Title",
        )
        assert data.title == "Custom Title"

    def test_default_title(self):
        data = build_sankey_from_energy(
            consumption=5.0,
            production=0.0,
            baselines={"washer": 1.0},
        )
        assert data.title == "Energiefluss"

    def test_no_baselines_no_zones(self):
        """Only consumption, no baselines, no zones → single flow."""
        data = build_sankey_from_energy(
            consumption=5.0,
            production=0.0,
            baselines={},
        )
        assert len(data.nodes) == 2  # grid + total
        assert len(data.flows) == 1

    def test_zero_baseline_skipped(self):
        """Devices with 0 kWh should be skipped."""
        data = build_sankey_from_energy(
            consumption=5.0,
            production=0.0,
            baselines={"washer": 1.5, "unused": 0.0},
        )
        node_ids = [n.id for n in data.nodes]
        assert "dev_unused" not in node_ids
        assert "dev_washer" in node_ids

    def test_flow_values_positive(self):
        data = build_sankey_from_energy(
            consumption=10.0,
            production=3.0,
            baselines={"washer": 1.5, "dryer": 3.5},
        )
        for flow in data.flows:
            assert flow.value >= 0

    def test_unit_is_kwh(self):
        data = build_sankey_from_energy(
            consumption=5.0,
            production=0.0,
            baselines={"washer": 1.0},
        )
        assert data.unit == "kWh"
