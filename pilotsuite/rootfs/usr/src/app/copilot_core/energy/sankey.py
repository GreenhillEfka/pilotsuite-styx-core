"""Sankey Diagram Generator — Pure SVG energy flow visualization.

Renders energy flow diagrams showing:
- Sources (Grid, Solar/PV, Battery) on the left
- Consumers (devices/zones) on the right
- Flow widths proportional to energy (kWh or Watts)

No external dependencies — pure Python SVG generation.
"""

import html
import math
from dataclasses import dataclass, field


@dataclass
class SankeyNode:
    """A node in the Sankey diagram."""
    id: str
    label: str
    value: float  # total flow through this node
    color: str = "#60a5fa"
    category: str = "device"  # source, device, storage, zone


@dataclass
class SankeyFlow:
    """A flow (link) between two nodes."""
    source: str
    target: str
    value: float
    color: str | None = None  # inherits from source if None


@dataclass
class SankeyData:
    """Complete Sankey diagram data."""
    nodes: list[SankeyNode] = field(default_factory=list)
    flows: list[SankeyFlow] = field(default_factory=list)
    title: str = ""
    unit: str = "W"


# ─── Color palettes ──────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "source": {"grid": "#60a5fa", "solar": "#fbbf24", "battery": "#34d399"},
    "device": {
        "washer": "#f472b6",
        "dryer": "#fb923c",
        "dishwasher": "#a78bfa",
        "ev_charger": "#2dd4bf",
        "heat_pump": "#f87171",
        "hvac": "#818cf8",
        "default": "#94a3b8",
    },
    "zone": "#38bdf8",
    "storage": "#10b981",
}

DARK_THEME = {
    "bg": "#0a0e14",
    "text": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "node_stroke": "#1e293b",
    "flow_opacity": 0.35,
    "node_opacity": 0.9,
}

LIGHT_THEME = {
    "bg": "#ffffff",
    "text": "#1e293b",
    "text_secondary": "#64748b",
    "node_stroke": "#e2e8f0",
    "flow_opacity": 0.3,
    "node_opacity": 0.85,
}


def get_device_color(device_type: str) -> str:
    """Get color for a device type."""
    return CATEGORY_COLORS["device"].get(
        device_type, CATEGORY_COLORS["device"]["default"]
    )


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class SankeyRenderer:
    """Pure SVG Sankey diagram renderer."""

    def __init__(
        self,
        width: int = 700,
        height: int = 400,
        theme: str = "dark",
        node_width: int = 20,
        node_padding: int = 15,
        margin: int = 40,
    ):
        self.width = width
        self.height = height
        self.theme = DARK_THEME if theme == "dark" else LIGHT_THEME
        self.theme_name = theme
        self.node_width = node_width
        self.node_padding = node_padding
        self.margin = margin

        # Usable area
        self._left = margin + 80  # space for source labels
        self._right = width - margin - 80  # space for target labels
        self._top = margin + 20  # space for title
        self._bottom = height - margin

    def render(self, data: SankeyData) -> str:
        """Render SankeyData to SVG string."""
        if not data.flows:
            return self._render_empty(data.title)

        # Separate sources and targets
        source_ids = set()
        target_ids = set()
        for flow in data.flows:
            source_ids.add(flow.source)
            target_ids.add(flow.target)

        # Nodes that are only sources (left side)
        left_ids = source_ids - target_ids
        # Nodes that are only targets (right side)
        right_ids = target_ids - source_ids
        # Nodes that are both (middle) — for now treat as right
        middle_ids = source_ids & target_ids
        right_ids = right_ids | middle_ids

        node_map = {n.id: n for n in data.nodes}

        # Calculate node positions
        left_nodes = self._layout_column(
            [node_map[nid] for nid in left_ids if nid in node_map],
            self._left,
        )
        right_nodes = self._layout_column(
            [node_map[nid] for nid in right_ids if nid in node_map],
            self._right,
        )

        all_positioned = {**left_nodes, **right_nodes}

        # Build SVG
        parts = [self._svg_header(data.title)]

        # Render flows first (behind nodes)
        for flow in data.flows:
            if flow.source in all_positioned and flow.target in all_positioned:
                parts.append(self._render_flow(flow, all_positioned, data))

        # Render nodes
        for nid, pos in all_positioned.items():
            if nid in node_map:
                parts.append(self._render_node(node_map[nid], pos, nid in left_ids))

        # Legend
        parts.append(self._render_legend(data))

        parts.append("</svg>")
        return "\n".join(parts)

    def _layout_column(
        self, nodes: list[SankeyNode], x: float
    ) -> dict[str, dict]:
        """Layout nodes vertically in a column, returns {id: {x, y, height}}."""
        if not nodes:
            return {}

        # Sort by value descending
        nodes.sort(key=lambda n: n.value, reverse=True)

        total_value = sum(n.value for n in nodes)
        if total_value <= 0:
            total_value = 1.0

        usable_height = (self._bottom - self._top) - self.node_padding * (len(nodes) - 1)
        if usable_height < 20:
            usable_height = 20

        result = {}
        y = self._top

        for node in nodes:
            fraction = node.value / total_value
            node_height = max(fraction * usable_height, 8)  # min 8px
            result[node.id] = {
                "x": x,
                "y": y,
                "height": node_height,
                "value": node.value,
            }
            y += node_height + self.node_padding

        return result

    def _svg_header(self, title: str) -> str:
        """Generate SVG header with styles."""
        bg = self.theme["bg"]
        text_color = self.theme["text"]
        escaped_title = html.escape(title) if title else ""

        title_svg = ""
        if escaped_title:
            title_svg = (
                f'<text x="{self.width // 2}" y="{self.margin - 5}" '
                f'text-anchor="middle" fill="{text_color}" '
                f'font-size="14" font-weight="600">{escaped_title}</text>'
            )

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
<rect width="{self.width}" height="{self.height}" fill="{bg}" rx="8"/>
<style>
  text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .flow {{ transition: opacity 0.2s; }}
  .flow:hover {{ opacity: 0.7 !important; }}
  .node-rect {{ transition: opacity 0.2s; }}
  .node-rect:hover {{ opacity: 1 !important; stroke-width: 2; }}
</style>
{title_svg}"""

    def _render_node(
        self, node: SankeyNode, pos: dict, is_left: bool
    ) -> str:
        """Render a single node rectangle with label."""
        x = pos["x"]
        y = pos["y"]
        h = pos["height"]
        color = node.color
        text_color = self.theme["text"]
        opacity = self.theme["node_opacity"]
        stroke = self.theme["node_stroke"]

        # Label position
        if is_left:
            label_x = x - 8
            anchor = "end"
        else:
            label_x = x + self.node_width + 8
            anchor = "start"

        label_y = y + h / 2 + 4
        escaped_label = html.escape(node.label)

        value_text = f"{node.value:.1f}" if node.value < 1000 else f"{node.value:.0f}"

        return f"""<rect class="node-rect" x="{x}" y="{y:.1f}" width="{self.node_width}" height="{h:.1f}" fill="{color}" opacity="{opacity}" stroke="{stroke}" stroke-width="1" rx="3"/>
<text x="{label_x}" y="{label_y:.1f}" text-anchor="{anchor}" fill="{text_color}" font-size="11">{escaped_label}</text>
<text x="{label_x}" y="{label_y + 13:.1f}" text-anchor="{anchor}" fill="{self.theme['text_secondary']}" font-size="9">{value_text} W</text>"""

    def _render_flow(
        self, flow: SankeyFlow, positions: dict, data: SankeyData
    ) -> str:
        """Render a flow as a bezier curve."""
        src = positions[flow.source]
        tgt = positions[flow.target]

        # Flow width proportional to value
        total = sum(f.value for f in data.flows)
        if total <= 0:
            total = 1.0

        usable = self._bottom - self._top
        flow_height = max((flow.value / total) * usable * 0.6, 2)

        # Source and target y-offsets (center flow on node)
        src_x = src["x"] + self.node_width
        src_y = src["y"] + src["height"] / 2
        tgt_x = tgt["x"]
        tgt_y = tgt["y"] + tgt["height"] / 2

        # Control points for smooth bezier
        cx = (src_x + tgt_x) / 2

        # Upper path
        y1_top = src_y - flow_height / 2
        y1_bot = src_y + flow_height / 2
        y2_top = tgt_y - flow_height / 2
        y2_bot = tgt_y + flow_height / 2

        path = (
            f"M {src_x},{y1_top:.1f} "
            f"C {cx:.1f},{y1_top:.1f} {cx:.1f},{y2_top:.1f} {tgt_x},{y2_top:.1f} "
            f"L {tgt_x},{y2_bot:.1f} "
            f"C {cx:.1f},{y2_bot:.1f} {cx:.1f},{y1_bot:.1f} {src_x},{y1_bot:.1f} Z"
        )

        color = flow.color or positions.get(flow.source, {}).get("color", "#60a5fa")
        # Try to get color from source node in data
        for n in data.nodes:
            if n.id == flow.source:
                color = flow.color or n.color
                break

        opacity = self.theme["flow_opacity"]

        return (
            f'<path class="flow" d="{path}" fill="{color}" '
            f'opacity="{opacity}" stroke="none">'
            f"<title>{html.escape(flow.source)} → {html.escape(flow.target)}: "
            f"{flow.value:.1f} {data.unit}</title></path>"
        )

    def _render_legend(self, data: SankeyData) -> str:
        """Render a small legend at the bottom."""
        y = self.height - 15
        items = []
        seen = set()

        for node in data.nodes:
            cat = node.category
            if cat not in seen:
                seen.add(cat)
                items.append((cat.title(), node.color))

        if not items:
            return ""

        parts = []
        x = self.margin
        for label, color in items:
            parts.append(
                f'<rect x="{x}" y="{y - 8}" width="10" height="10" '
                f'fill="{color}" rx="2"/>'
            )
            parts.append(
                f'<text x="{x + 14}" y="{y}" fill="{self.theme["text_secondary"]}" '
                f'font-size="9">{html.escape(label)}</text>'
            )
            x += len(label) * 6 + 30

        return "\n".join(parts)

    def _render_empty(self, title: str) -> str:
        """Render empty state SVG."""
        bg = self.theme["bg"]
        text_color = self.theme["text_secondary"]
        escaped = html.escape(title) if title else "Energy Flow"

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">
<rect width="{self.width}" height="{self.height}" fill="{bg}" rx="8"/>
<text x="{self.width // 2}" y="{self.height // 2 - 10}" text-anchor="middle" fill="{text_color}" font-size="14" font-family="sans-serif">{escaped}</text>
<text x="{self.width // 2}" y="{self.height // 2 + 15}" text-anchor="middle" fill="{text_color}" font-size="11" font-family="sans-serif">Keine Energiedaten verfuegbar</text>
</svg>"""


def build_sankey_from_energy(
    consumption: float,
    production: float,
    baselines: dict[str, float],
    zone_data: dict | None = None,
    title: str = "",
) -> SankeyData:
    """Build SankeyData from energy service data.

    Args:
        consumption: Total consumption today (kWh)
        production: Total production/solar today (kWh)
        baselines: Device type → daily kWh baselines
        zone_data: Optional zone breakdown {zone_name: power_watts}
        title: Diagram title
    """
    nodes = []
    flows = []

    # Sources
    grid_value = max(consumption - production, 0.0)
    if grid_value > 0:
        nodes.append(SankeyNode(
            id="grid", label="Netz", value=grid_value,
            color=CATEGORY_COLORS["source"]["grid"], category="source",
        ))

    if production > 0:
        nodes.append(SankeyNode(
            id="solar", label="Solar/PV", value=production,
            color=CATEGORY_COLORS["source"]["solar"], category="source",
        ))

    # If zone data provided, use zones as targets
    if zone_data:
        total_zone_power = sum(zone_data.values()) or 1.0
        for zone_name, power in zone_data.items():
            zid = f"zone_{zone_name.lower().replace(' ', '_')}"
            nodes.append(SankeyNode(
                id=zid, label=zone_name, value=power,
                color=CATEGORY_COLORS["zone"], category="zone",
            ))

            # Distribute sources proportionally
            if grid_value > 0:
                grid_share = power * (grid_value / (grid_value + production)) if (grid_value + production) > 0 else power
                flows.append(SankeyFlow(
                    source="grid", target=zid, value=round(grid_share, 2),
                ))
            if production > 0:
                solar_share = power * (production / (grid_value + production)) if (grid_value + production) > 0 else 0
                flows.append(SankeyFlow(
                    source="solar", target=zid, value=round(solar_share, 2),
                ))
    else:
        # Use baselines as device breakdown
        total_baseline = sum(baselines.values()) or 1.0
        for device_type, daily_kwh in baselines.items():
            if daily_kwh <= 0:
                continue
            did = f"dev_{device_type}"
            label = device_type.replace("_", " ").title()
            nodes.append(SankeyNode(
                id=did, label=label, value=daily_kwh,
                color=get_device_color(device_type), category="device",
            ))

            # Distribute sources proportionally
            share = daily_kwh / total_baseline
            if grid_value > 0:
                flows.append(SankeyFlow(
                    source="grid", target=did,
                    value=round(grid_value * share, 2),
                ))
            if production > 0:
                flows.append(SankeyFlow(
                    source="solar", target=did,
                    value=round(production * share, 2),
                ))

    # If no detailed targets were created, add a simple total consumption sink.
    if consumption > 0 and not flows:
        if not any(n.id == "grid" for n in nodes):
            nodes.append(SankeyNode(
                id="grid", label="Netz", value=consumption,
                color=CATEGORY_COLORS["source"]["grid"], category="source",
            ))
        if not any(n.id == "total" for n in nodes):
            nodes.append(SankeyNode(
                id="total", label="Verbrauch", value=consumption,
                color=CATEGORY_COLORS["device"]["default"], category="device",
            ))
        flows.append(SankeyFlow(source="grid", target="total", value=consumption))

    return SankeyData(
        nodes=nodes,
        flows=flows,
        title=title or "Energiefluss",
        unit="kWh",
    )
