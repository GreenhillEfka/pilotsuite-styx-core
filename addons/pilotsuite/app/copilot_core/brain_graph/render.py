"""
DOT/SVG rendering for brain graph visualization.
"""

import subprocess
from typing import Dict, List, Optional, Any


class GraphRenderer:
    """Renders brain graph as DOT/SVG with bounded complexity."""
    
    def __init__(
        self,
        max_render_nodes: int = 120,
        max_render_edges: int = 300
    ):
        self.max_render_nodes = max_render_nodes
        self.max_render_edges = max_render_edges
    
    def render_svg(
        self,
        graph_state: Dict[str, Any],
        layout: str = "dot",
        theme: str = "light", 
        label_style: str = "short"
    ) -> bytes:
        """Render graph state as SVG."""
        
        # Apply rendering limits
        nodes = graph_state.get("nodes", [])
        edges = graph_state.get("edges", [])
        
        # Sort by salience and limit
        nodes = sorted(nodes, key=lambda n: n.get("score", 0), reverse=True)[:self.max_render_nodes]
        node_ids = {n["id"] for n in nodes}
        
        # Filter edges to only include those between rendered nodes
        valid_edges = [e for e in edges if e.get("from") in node_ids and e.get("to") in node_ids]
        valid_edges = sorted(valid_edges, key=lambda e: e.get("weight", 0), reverse=True)[:self.max_render_edges]
        
        # Generate DOT
        dot_content = self._generate_dot(nodes, valid_edges, theme, label_style)
        
        # Render with Graphviz
        return self._dot_to_svg(dot_content, layout)
    
    def _generate_dot(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        theme: str,
        label_style: str
    ) -> str:
        """Generate DOT format from nodes and edges."""
        
        # Theme colors
        if theme == "dark":
            bg_color = "#2b2b2b"
            text_color = "#ffffff" 
            node_colors = {
                "entity": "#4CAF50",
                "zone": "#2196F3",
                "device": "#FF9800",
                "person": "#E91E63",
                "concept": "#9C27B0", 
                "module": "#607D8B",
                "event": "#FF5722"
            }
            edge_color = "#666666"
        else:  # light theme
            bg_color = "#ffffff"
            text_color = "#000000"
            node_colors = {
                "entity": "#8BC34A",
                "zone": "#03A9F4", 
                "device": "#FFC107",
                "person": "#F06292",
                "concept": "#AB47BC",
                "module": "#78909C",
                "event": "#FF7043"
            }
            edge_color = "#999999"
        
        dot_lines = [
            f'digraph BrainGraph {{',
            f'    bgcolor="{bg_color}";',
            f'    node [fontname="Arial", fontcolor="{text_color}"];',
            f'    edge [color="{edge_color}", fontcolor="{text_color}"];',
            ''
        ]
        
        # Add nodes
        for node in nodes:
            node_id = self._escape_dot_id(node["id"])
            kind = node.get("kind", "entity")
            color = node_colors.get(kind, node_colors["entity"])
            
            # Choose label based on style
            if label_style == "full":
                label = self._escape_dot_string(node.get("label", node["id"]))
                if node.get("domain"):
                    label += f"\\n({node['domain']})"
                if node.get("score", 0) > 0:
                    label += f"\\nscore: {node['score']:.1f}"
            else:  # short
                label = self._escape_dot_string(node.get("label", node["id"]))
                if len(label) > 20:
                    label = label[:17] + "..."
            
            # Node shape based on kind
            shape = "ellipse"
            if kind == "zone":
                shape = "box"
            elif kind == "concept":
                shape = "diamond"
            elif kind == "module":
                shape = "hexagon"
            
            dot_lines.append(
                f'    {node_id} [label="{label}", fillcolor="{color}", style="filled", shape="{shape}"];'
            )
        
        dot_lines.append('')
        
        # Add edges
        for edge in edges:
            from_id = self._escape_dot_id(edge["from"])
            to_id = self._escape_dot_id(edge["to"])
            edge_type = edge.get("type", "")
            weight = edge.get("weight", 1.0)
            
            # Edge style based on type
            style = "solid"
            arrowhead = "normal"
            
            if edge_type in ["correlates", "observed_with"]:
                style = "dashed"
                arrowhead = "none"
            elif edge_type == "in_zone":
                style = "dotted"
            
            # Line width based on weight
            penwidth = max(1.0, min(5.0, weight))
            
            # Edge label
            edge_label = edge_type.replace("_", " ") if edge_type else ""
            
            dot_lines.append(
                f'    {from_id} -> {to_id} [label="{edge_label}", style="{style}", arrowhead="{arrowhead}", penwidth="{penwidth:.1f}"];'
            )
        
        dot_lines.extend(['', '}'])
        
        return '\n'.join(dot_lines)
    
    def _dot_to_svg(self, dot_content: str, layout: str) -> bytes:
        """Convert DOT content to SVG using Graphviz."""
        if layout not in ["dot", "neato", "fdp", "circo", "twopi"]:
            layout = "dot"
            
        try:
            # Run Graphviz
            process = subprocess.run(
                [layout, "-Tsvg"],
                input=dot_content.encode('utf-8'),
                capture_output=True,
                timeout=30
            )
            
            if process.returncode != 0:
                # Fallback to simple error SVG
                error_msg = f"Graphviz error: {process.stderr.decode('utf-8', errors='ignore')}"
                return self._generate_error_svg(error_msg)
            
            return process.stdout
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            # Fallback to simple error SVG
            return self._generate_error_svg(f"Rendering failed: {str(e)}")
    
    def _generate_error_svg(self, message: str) -> bytes:
        """Generate a simple error SVG."""
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">
    <rect width="400" height="200" fill="#f8f8f8" stroke="#ddd"/>
    <text x="200" y="100" text-anchor="middle" font-family="Arial" font-size="14" fill="#666">
        {self._escape_xml(message)}
    </text>
    <text x="200" y="130" text-anchor="middle" font-family="Arial" font-size="12" fill="#999">
        Graph rendering unavailable
    </text>
</svg>'''
        return svg_content.encode('utf-8')
    
    def _escape_dot_id(self, node_id: str) -> str:
        """Escape node ID for DOT format."""
        # Replace problematic characters with underscores
        safe_id = ""
        for char in node_id:
            if char.isalnum() or char in "_":
                safe_id += char
            else:
                safe_id += "_"
        
        # Ensure starts with letter or underscore
        if safe_id and safe_id[0].isdigit():
            safe_id = "n" + safe_id
            
        return safe_id or "unknown"
    
    def _escape_dot_string(self, text: str) -> str:
        """Escape string for DOT label."""
        if not isinstance(text, str):
            text = str(text)
        return text.replace('"', '\\"').replace('\n', '\\n')
    
    def _escape_xml(self, text: str) -> str:
        """Escape text for XML/SVG."""
        if not isinstance(text, str):
            text = str(text)
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&apos;'))