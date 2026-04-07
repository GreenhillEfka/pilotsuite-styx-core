"""Knowledge Transfer API Contract (P2-008).

Provides API for exporting/importing learned knowledge between PilotSuite instances.
Supports knowledge graph serialization, migration tools, validation, and conflict resolution.

Features:
- Export knowledge packages (graph + learned patterns)
- Import knowledge with validation
- Conflict detection and resolution strategies
- Knowledge graph serialization (JSON, GraphML)
- Migration tools for version upgrades
- Transfer logging and audit trail
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from ..collective_intelligence.models import KnowledgeItem
from ..knowledge_graph.models import Node, Edge, NodeType, EdgeType, GraphResult

logger = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """Strategies for resolving knowledge conflicts during import."""
    SKIP = "skip"                    # Skip conflicting items
    OVERWRITE = "overwrite"          # Overwrite existing with imported
    MERGE = "merge"                  # Merge properties (union)
    KEEP_BOTH = "keep_both"          # Keep both, rename imported
    HIGHEST_CONFIDENCE = "highest_confidence"  # Keep item with higher confidence


class ExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    GRAPHML = "graphml"
    TAR_GZ = "tar.gz"


class ValidationError(Exception):
    """Raised when knowledge validation fails."""
    pass


class ConflictError(Exception):
    """Raised when unresolvable conflicts are detected."""
    pass


@dataclass
class ExportPackage:
    """Represents an exportable knowledge package."""
    package_id: str
    version: str
    source_node_id: str
    created_at: float = field(default_factory=time.time)
    knowledge_items: List[Dict[str, Any]] = field(default_factory=list)
    graph_nodes: List[Dict[str, Any]] = field(default_factory=list)
    graph_edges: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute package checksum for integrity verification."""
        content = json.dumps({
            "knowledge_items": self.knowledge_items,
            "graph_nodes": self.graph_nodes,
            "graph_edges": self.graph_edges,
            "version": self.version,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportPackage":
        """Create from dictionary."""
        return cls(**data)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "ExportPackage":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ImportResult:
    """Result of a knowledge import operation."""
    success: bool
    imported_count: int
    skipped_count: int
    conflict_count: int
    error_count: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    imported_knowledge_ids: List[str] = field(default_factory=list)
    imported_node_ids: List[str] = field(default_factory=list)
    imported_edge_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TransferResult:
    """Result of a knowledge transfer operation."""
    success: bool
    transfer_id: str
    source_node_id: str
    target_node_id: str
    timestamp: float = field(default_factory=time.time)
    package_id: Optional[str] = None
    import_result: Optional[ImportResult] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class MigrationPlan:
    """Plan for migrating knowledge between versions."""
    source_version: str
    target_version: str
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    estimated_items: int = 0
    risks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class KnowledgeTransferAPI:
    """
    Knowledge Transfer API for PilotSuite.

    Implements P2-008 Knowledge Transfer API Contract:
    1. Export/import learned knowledge
    2. Knowledge graph serialization
    3. Migration tools for knowledge transfer
    4. Validation and conflict resolution
    """

    def __init__(
        self,
        export_dir: Optional[str] = None,
        import_dir: Optional[str] = None,
        max_package_size_mb: int = 100,
    ):
        """
        Initialize Knowledge Transfer API.

        Args:
            export_dir: Directory for exported packages
            import_dir: Directory for incoming packages
            max_package_size_mb: Maximum package size in MB
        """
        self.export_dir = export_dir or "/data/knowledge/exports"
        self.import_dir = import_dir or "/data/knowledge/imports"
        self.max_package_size_mb = max_package_size_mb

        # Ensure directories exist
        os.makedirs(self.export_dir, exist_ok=True)
        os.makedirs(self.import_dir, exist_ok=True)

        # In-memory stores (in production, these would be backed by persistent storage)
        self._knowledge_items: Dict[str, KnowledgeItem] = {}
        self._graph_nodes: Dict[str, Node] = {}
        self._graph_edges: Dict[str, Edge] = {}

        # Transfer log
        self._transfer_log: List[TransferResult] = []

        # Version tracking
        self._schema_version = "1.0.0"

    # ==================== Export Operations ====================

    def export_knowledge(
        self,
        package_name: str,
        knowledge_ids: Optional[List[str]] = None,
        include_graph: bool = True,
        node_filter: Optional[Set[NodeType]] = None,
        format: ExportFormat = ExportFormat.JSON,
    ) -> ExportPackage:
        """
        Export knowledge to a package.

        Args:
            package_name: Name for the export package
            knowledge_ids: Specific knowledge IDs to export (None = all)
            include_graph: Whether to include knowledge graph
            node_filter: Filter nodes by type (None = all types)
            format: Export format

        Returns:
            ExportPackage with serialized knowledge
        """
        logger.info(f"Exporting knowledge package: {package_name}")

        package = ExportPackage(
            package_id=self._generate_package_id(package_name),
            version=self._schema_version,
            source_node_id=self._get_node_id(),
            metadata={
                "export_format": format.value,
                "include_graph": include_graph,
                "node_filter": [nt.value for nt in node_filter] if node_filter else None,
            }
        )

        # Export knowledge items
        if knowledge_ids:
            for kid in knowledge_ids:
                if kid in self._knowledge_items:
                    package.knowledge_items.append(
                        self._knowledge_items[kid].to_dict()
                    )
        else:
            for item in self._knowledge_items.values():
                package.knowledge_items.append(item.to_dict())

        # Export graph if requested
        if include_graph:
            for node_id, node in self._graph_nodes.items():
                if node_filter is None or node.type in node_filter:
                    package.graph_nodes.append(node.to_dict())

            for edge_id, edge in self._graph_edges.items():
                # Only include edges where both nodes are exported
                if edge.source in self._graph_nodes and edge.target in self._graph_nodes:
                    if node_filter is None or (
                        self._graph_nodes[edge.source].type in node_filter and
                        self._graph_nodes[edge.target].type in node_filter
                    ):
                        package.graph_edges.append(edge.to_dict())

        # Save to file
        export_path = self._save_package(package, format)
        logger.info(f"Exported package to: {export_path}")

        return package

    def export_to_file(
        self,
        package: ExportPackage,
        format: ExportFormat = ExportFormat.JSON,
    ) -> str:
        """
        Save an export package to file.

        Args:
            package: Package to save
            format: Export format

        Returns:
            Path to saved file
        """
        return self._save_package(package, format)

    def _save_package(self, package: ExportPackage, format: ExportFormat) -> str:
        """Save package to file in specified format."""
        timestamp = datetime.fromtimestamp(package.created_at).strftime("%Y%m%d_%H%M%S")
        base_filename = f"{package.package_id}_{timestamp}"

        if format == ExportFormat.JSON:
            filepath = os.path.join(self.export_dir, f"{base_filename}.json")
            with open(filepath, "w") as f:
                f.write(package.to_json())

        elif format == ExportFormat.GRAPHML:
            filepath = os.path.join(self.export_dir, f"{base_filename}.graphml")
            graphml_content = self._to_graphml(package)
            with open(filepath, "w") as f:
                f.write(graphml_content)

        elif format == ExportFormat.TAR_GZ:
            filepath = os.path.join(self.export_dir, f"{base_filename}.tar.gz")
            # Create temp directory for package contents
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write metadata
                meta_path = os.path.join(tmpdir, "metadata.json")
                with open(meta_path, "w") as f:
                    json.dump({
                        "package_id": package.package_id,
                        "version": package.version,
                        "source_node_id": package.source_node_id,
                        "created_at": package.created_at,
                        "checksum": package.checksum,
                    }, f, indent=2)

                # Write knowledge items
                knowledge_path = os.path.join(tmpdir, "knowledge.json")
                with open(knowledge_path, "w") as f:
                    json.dump(package.knowledge_items, f, indent=2)

                # Write graph
                graph_path = os.path.join(tmpdir, "graph.json")
                with open(graph_path, "w") as f:
                    json.dump({
                        "nodes": package.graph_nodes,
                        "edges": package.graph_edges,
                    }, f, indent=2)

                # Create tar.gz
                with tarfile.open(filepath, "w:gz") as tar:
                    tar.add(tmpdir, arcname="package")

        return filepath

    def _to_graphml(self, package: ExportPackage) -> str:
        """Convert package to GraphML format."""
        # GraphML header
        graphml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
            '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
            '  <key id="properties" for="node" attr.name="properties" attr.type="string"/>',
            '  <key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
            '  <key id="confidence" for="edge" attr.name="confidence" attr.type="double"/>',
            '  <graph edgedirected="true">',
        ]

        # Add nodes
        for node_data in package.graph_nodes:
            graphml.append(f'    <node id="{node_data["id"]}">')
            graphml.append(f'      <data key="label">{node_data["label"]}</data>')
            graphml.append(f'      <data key="type">{node_data["type"]}</data>')
            props = json.dumps(node_data.get("properties", {}))
            graphml.append(f'      <data key="properties">{props}</data>')
            graphml.append('    </node>')

        # Add edges
        for edge_data in package.graph_edges:
            graphml.append(
                f'    <edge source="{edge_data["source"]}" target="{edge_data["target"]}">'
            )
            graphml.append(f'      <data key="weight">{edge_data.get("weight", 1.0)}</data>')
            graphml.append(
                f'      <data key="confidence">{edge_data.get("confidence", 0.0)}</data>'
            )
            graphml.append('    </edge>')

        graphml.extend([
            '  </graph>',
            '</graphml>',
        ])

        return "\n".join(graphml)

    # ==================== Import Operations ====================

    def import_knowledge(
        self,
        package: ExportPackage,
        conflict_strategy: ConflictStrategy = ConflictStrategy.HIGHEST_CONFIDENCE,
        validate: bool = True,
    ) -> ImportResult:
        """
        Import knowledge from a package.

        Args:
            package: Package to import
            conflict_strategy: How to handle conflicts
            validate: Whether to validate before importing

        Returns:
            ImportResult with import statistics
        """
        logger.info(f"Importing knowledge package: {package.package_id}")

        result = ImportResult(
            success=True,
            imported_count=0,
            skipped_count=0,
            conflict_count=0,
            error_count=0,
        )

        # Validate package
        if validate:
            validation_errors = self._validate_package(package)
            if validation_errors:
                result.success = False
                result.errors.extend(validation_errors)
                result.error_count = len(validation_errors)
                return result

        # Check for conflicts
        conflicts = self._detect_conflicts(package)
        if conflicts and conflict_strategy == ConflictStrategy.SKIP:
            result.skipped_count = len(conflicts)
            result.warnings.append(f"Skipped {len(conflicts)} conflicting items")

        # Import knowledge items
        for item_data in package.knowledge_items:
            try:
                item = KnowledgeItem.from_dict(item_data)

                # Check for conflicts
                if item.knowledge_hash in self._knowledge_items:
                    existing = self._knowledge_items[item.knowledge_hash]
                    conflict = self._resolve_conflict(
                        existing, item, conflict_strategy
                    )
                    if conflict is None:
                        result.skipped_count += 1
                        continue
                    elif conflict == "existing":
                        result.conflict_count += 1
                        continue
                    # else: import the new item

                self._knowledge_items[item.knowledge_hash] = item
                result.imported_count += 1
                result.imported_knowledge_ids.append(item.knowledge_id)

            except Exception as e:
                result.error_count += 1
                result.errors.append(f"Failed to import knowledge item: {e}")
                result.success = False

        # Import graph nodes
        for node_data in package.graph_nodes:
            try:
                node = Node.from_dict(node_data)

                if node.id in self._graph_nodes:
                    existing = self._graph_nodes[node.id]
                    conflict = self._resolve_conflict(
                        existing, node, conflict_strategy
                    )
                    if conflict is None:
                        result.skipped_count += 1
                        continue
                    elif conflict == "existing":
                        result.conflict_count += 1
                        continue

                self._graph_nodes[node.id] = node
                result.imported_count += 1
                result.imported_node_ids.append(node.id)

            except Exception as e:
                result.error_count += 1
                result.errors.append(f"Failed to import node {node_data.get('id')}: {e}")
                result.success = False

        # Import graph edges
        for edge_data in package.graph_edges:
            try:
                edge = Edge.from_dict(edge_data)

                if edge.id in self._graph_edges:
                    existing = self._graph_edges[edge.id]
                    conflict = self._resolve_conflict(
                        existing, edge, conflict_strategy
                    )
                    if conflict is None:
                        result.skipped_count += 1
                        continue
                    elif conflict == "existing":
                        result.conflict_count += 1
                        continue

                self._graph_edges[edge.id] = edge
                result.imported_count += 1
                result.imported_edge_ids.append(edge.id)

            except Exception as e:
                result.error_count += 1
                result.errors.append(f"Failed to import edge: {e}")
                result.success = False

        logger.info(
            f"Import complete: {result.imported_count} imported, "
            f"{result.skipped_count} skipped, {result.conflict_count} conflicts, "
            f"{result.error_count} errors"
        )

        return result

    def import_from_file(
        self,
        filepath: str,
        format: Optional[ExportFormat] = None,
        conflict_strategy: ConflictStrategy = ConflictStrategy.HIGHEST_CONFIDENCE,
    ) -> ImportResult:
        """
        Import knowledge from a file.

        Args:
            filepath: Path to import file
            format: File format (auto-detected if None)
            conflict_strategy: How to handle conflicts

        Returns:
            ImportResult with import statistics
        """
        # Auto-detect format
        if format is None:
            if filepath.endswith(".json"):
                format = ExportFormat.JSON
            elif filepath.endswith(".graphml"):
                format = ExportFormat.GRAPHML
            elif filepath.endswith(".tar.gz"):
                format = ExportFormat.TAR_GZ
            else:
                return ImportResult(
                    success=False,
                    imported_count=0,
                    error_count=1,
                    errors=[f"Unknown file format: {filepath}"],
                )

        # Load package
        if format == ExportFormat.TAR_GZ:
            package = self._load_tar_package(filepath)
        elif format == ExportFormat.GRAPHML:
            package = self._load_graphml_package(filepath)
        else:
            with open(filepath, "r") as f:
                package = ExportPackage.from_json(f.read())

        # Verify checksum
        if package.checksum and package.checksum != package._compute_checksum():
            return ImportResult(
                success=False,
                imported_count=0,
                error_count=1,
                errors=["Package checksum mismatch - file may be corrupted"],
            )

        return self.import_knowledge(package, conflict_strategy)

    def _load_tar_package(self, filepath: str) -> ExportPackage:
        """Load package from tar.gz file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(filepath, "r:gz") as tar:
                tar.extractall(tmpdir)

            # Load metadata
            with open(os.path.join(tmpdir, "package", "metadata.json")) as f:
                meta = json.load(f)

            # Load knowledge
            with open(os.path.join(tmpdir, "package", "knowledge.json")) as f:
                knowledge_items = json.load(f)

            # Load graph
            with open(os.path.join(tmpdir, "package", "graph.json")) as f:
                graph_data = json.load(f)

            return ExportPackage(
                package_id=meta["package_id"],
                version=meta["version"],
                source_node_id=meta["source_node_id"],
                created_at=meta["created_at"],
                checksum=meta.get("checksum", ""),
                knowledge_items=knowledge_items,
                graph_nodes=graph_data.get("nodes", []),
                graph_edges=graph_data.get("edges", []),
            )

    def _load_graphml_package(self, filepath: str) -> ExportPackage:
        """Load package from GraphML file."""
        # Simplified GraphML parsing
        import xml.etree.ElementTree as ET

        tree = ET.parse(filepath)
        root = tree.getroot()
        ns = {"g": "http://graphml.graphdrawing.org/xmlns"}

        nodes = []
        edges = []

        for node_elem in root.findall(".//g:node", ns):
            node_id = node_elem.get("id")
            label = ""
            node_type = "entity"
            properties = {}

            for data in node_elem.findall("g:data", ns):
                key = data.get("key")
                if key == "label":
                    label = data.text or ""
                elif key == "type":
                    node_type = data.text or "entity"
                elif key == "properties":
                    properties = json.loads(data.text or "{}")

            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": label,
                "properties": properties,
                "created_at": int(time.time() * 1000),
                "updated_at": int(time.time() * 1000),
            })

        for edge_elem in root.findall(".//g:edge", ns):
            edges.append({
                "source": edge_elem.get("source"),
                "target": edge_elem.get("target"),
                "type": "relates_to",
                "weight": 1.0,
                "confidence": 0.5,
                "source_type": "imported",
                "evidence": {},
                "created_at": int(time.time() * 1000),
                "updated_at": int(time.time() * 1000),
            })

        return ExportPackage(
            package_id=f"graphml_{os.path.basename(filepath)}",
            version=self._schema_version,
            source_node_id="unknown",
            graph_nodes=nodes,
            graph_edges=edges,
        )

    # ==================== Validation ====================

    def _validate_package(self, package: ExportPackage) -> List[str]:
        """Validate an export package."""
        errors = []

        # Check version compatibility
        if package.version != self._schema_version:
            errors.append(
                f"Version mismatch: package {package.version} vs "
                f"current {self._schema_version}"
            )

        # Check checksum
        if package.checksum and package.checksum != package._compute_checksum():
            errors.append("Checksum mismatch - package may be corrupted")

        # Validate knowledge items
        for item_data in package.knowledge_items:
            if not item_data.get("knowledge_id"):
                errors.append("Knowledge item missing knowledge_id")
            if not item_data.get("knowledge_type"):
                errors.append("Knowledge item missing knowledge_type")
            if "payload" not in item_data:
                errors.append("Knowledge item missing payload")

        # Validate graph nodes
        for node_data in package.graph_nodes:
            if not node_data.get("id"):
                errors.append("Graph node missing id")
            if not node_data.get("type"):
                errors.append("Graph node missing type")

        # Validate graph edges
        for edge_data in package.graph_edges:
            if not edge_data.get("source"):
                errors.append("Graph edge missing source")
            if not edge_data.get("target"):
                errors.append("Graph edge missing target")

        return errors

    def _detect_conflicts(self, package: ExportPackage) -> List[Dict[str, Any]]:
        """Detect conflicts between package and existing knowledge."""
        conflicts = []

        # Check knowledge items
        for item_data in package.knowledge_items:
            item = KnowledgeItem.from_dict(item_data)
            if item.knowledge_hash in self._knowledge_items:
                existing = self._knowledge_items[item.knowledge_hash]
                conflicts.append({
                    "type": "knowledge_item",
                    "id": item.knowledge_hash,
                    "existing_confidence": existing.confidence,
                    "imported_confidence": item.confidence,
                })

        # Check graph nodes
        for node_data in package.graph_nodes:
            node_id = node_data["id"]
            if node_id in self._graph_nodes:
                existing = self._graph_nodes[node_id]
                conflicts.append({
                    "type": "graph_node",
                    "id": node_id,
                    "existing_updated": existing.updated_at,
                    "imported_updated": node_data.get("updated_at", 0),
                })

        return conflicts

    def _resolve_conflict(
        self,
        existing: Any,
        imported: Any,
        strategy: ConflictStrategy,
    ) -> Optional[str]:
        """
        Resolve a conflict between existing and imported items.

        Returns:
            "import" to use imported item
            "existing" to keep existing item
            None to skip both
        """
        if strategy == ConflictStrategy.SKIP:
            return None
        elif strategy == ConflictStrategy.OVERWRITE:
            return "import"
        elif strategy == ConflictStrategy.MERGE:
            # Merge logic - for now, prefer imported
            return "import"
        elif strategy == ConflictStrategy.KEEP_BOTH:
            # Rename imported - for now, prefer imported
            return "import"
        elif strategy == ConflictStrategy.HIGHEST_CONFIDENCE:
            existing_conf = getattr(existing, "confidence", 0.5)
            imported_conf = getattr(imported, "confidence", 0.5)
            return "import" if imported_conf > existing_conf else "existing"

        return "import"

    # ==================== Migration Tools ====================

    def create_migration_plan(
        self,
        source_version: str,
        target_version: str,
    ) -> MigrationPlan:
        """
        Create a migration plan between versions.

        Args:
            source_version: Current schema version
            target_version: Target schema version

        Returns:
            MigrationPlan with transformation steps
        """
        plan = MigrationPlan(
            source_version=source_version,
            target_version=target_version,
        )

        # Define transformations based on version diff
        transformations = []

        # Example: v1.0.0 -> v1.1.0 transformations
        if source_version == "1.0.0" and target_version >= "1.1.0":
            transformations.append({
                "type": "add_field",
                "target": "knowledge_item",
                "field": "migration_timestamp",
                "default": lambda: int(time.time()),
            })

        # Example: v1.x -> v2.0 transformations
        if source_version.startswith("1.") and target_version.startswith("2."):
            transformations.append({
                "type": "schema_upgrade",
                "description": "Major schema upgrade from v1 to v2",
                "risks": ["Data loss possible", "Incompatible with v1 readers"],
            })
            plan.risks.append("Major version upgrade - backup recommended")

        plan.transformations = transformations
        plan.estimated_items = (
            len(self._knowledge_items) +
            len(self._graph_nodes) +
            len(self._graph_edges)
        )

        return plan

    def execute_migration(
        self,
        package: ExportPackage,
        plan: MigrationPlan,
    ) -> ExportPackage:
        """
        Execute a migration on a package.

        Args:
            package: Package to migrate
            plan: Migration plan to execute

        Returns:
            Migrated package
        """
        logger.info(
            f"Executing migration: {plan.source_version} -> {plan.target_version}"
        )

        migrated = ExportPackage(
            package_id=package.package_id,
            version=plan.target_version,
            source_node_id=package.source_node_id,
            created_at=package.created_at,
            metadata={
                **package.metadata,
                "migrated_from": package.version,
                "migrated_at": time.time(),
            },
        )

        # Apply transformations
        for transform in plan.transformations:
            if transform["type"] == "add_field":
                if transform["target"] == "knowledge_item":
                    for item_data in package.knowledge_items:
                        if transform["field"] not in item_data:
                            item_data[transform["field"]] = transform["default"]()

            elif transform["type"] == "schema_upgrade":
                # Handle major version upgrade
                migrated.knowledge_items = self._upgrade_knowledge_v1_to_v2(
                    package.knowledge_items
                )
                migrated.graph_nodes = self._upgrade_nodes_v1_to_v2(
                    package.graph_nodes
                )
                migrated.graph_edges = self._upgrade_edges_v1_to_v2(
                    package.graph_edges
                )

        # Copy non-migrated data
        if plan.target_version < "2.0":
            migrated.knowledge_items = package.knowledge_items
            migrated.graph_nodes = package.graph_nodes
            migrated.graph_edges = package.graph_edges

        # Recompute checksum
        migrated.checksum = migrated._compute_checksum()

        return migrated

    def _upgrade_knowledge_v1_to_v2(
        self,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Upgrade knowledge items from v1 to v2 schema."""
        upgraded = []
        for item_data in items:
            # Add v2 fields
            item_data.setdefault("schema_version", "2.0.0")
            item_data.setdefault("lineage", [])
            upgraded.append(item_data)
        return upgraded

    def _upgrade_nodes_v1_to_v2(
        self,
        nodes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Upgrade graph nodes from v1 to v2 schema."""
        upgraded = []
        for node_data in nodes:
            node_data.setdefault("schema_version", "2.0.0")
            upgraded.append(node_data)
        return upgraded

    def _upgrade_edges_v1_to_v2(
        self,
        edges: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Upgrade graph edges from v1 to v2 schema."""
        upgraded = []
        for edge_data in edges:
            edge_data.setdefault("schema_version", "2.0.0")
            upgraded.append(edge_data)
        return upgraded

    # ==================== Utility Methods ====================

    def _generate_package_id(self, name: str) -> str:
        """Generate unique package ID."""
        timestamp = int(time.time() * 1000)
        content = f"{name}:{timestamp}"
        return f"pkg_{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def _get_node_id(self) -> str:
        """Get current node ID."""
        return os.environ.get("PILOTSUITE_NODE_ID", "unknown_node")

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge transfer statistics."""
        return {
            "knowledge_items": len(self._knowledge_items),
            "graph_nodes": len(self._graph_nodes),
            "graph_edges": len(self._graph_edges),
            "transfers": len(self._transfer_log),
            "export_dir": self.export_dir,
            "import_dir": self.import_dir,
            "schema_version": self._schema_version,
        }

    def log_transfer(self, result: TransferResult) -> None:
        """Log a transfer result."""
        self._transfer_log.append(result)

    def get_transfer_history(
        self,
        limit: int = 100,
    ) -> List[TransferResult]:
        """Get recent transfer history."""
        return self._transfer_log[-limit:]

    def clear_all(self) -> None:
        """Clear all knowledge and logs."""
        self._knowledge_items.clear()
        self._graph_nodes.clear()
        self._graph_edges.clear()
        self._transfer_log.clear()
