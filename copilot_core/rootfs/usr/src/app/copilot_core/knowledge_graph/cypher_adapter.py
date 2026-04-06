"""
Cypher Query Adapter for PilotSuite Knowledge Graph.

Provides a fluent API for building complex Cypher queries programmatically,
including query builders for common graph patterns used in PilotSuite.

Features:
- Fluent Cypher query builder
- Type-safe query construction
- Parameter binding
- Query templates for common patterns
- Query optimization hints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import EdgeType, NodeType

_LOGGER = logging.getLogger(__name__)


@dataclass
class MatchClause:
    """Represents a MATCH clause in Cypher."""

    pattern: str
    optional: bool = False
    variables: Dict[str, str] = field(default_factory=dict)


@dataclass
class WhereClause:
    """Represents a WHERE clause in Cypher."""

    conditions: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReturnClause:
    """Represents a RETURN clause in Cypher."""

    expressions: List[str] = field(default_factory=list)
    distinct: bool = False
    order_by: Optional[str] = None
    skip: Optional[int] = None
    limit: Optional[int] = None


@dataclass
class CypherBuilder:
    """
    Fluent builder for constructing Cypher queries.

    Example:
        builder = CypherBuilder()
        query = (builder
            .match("(n:Entity {id: $entity_id})")
            .optional_match("(n)-[r]-(neighbor)")
            .where("n.domain = $domain")
            .return_expr("n, r, neighbor")
            .limit(100)
            .build())
    """

    _matches: List[MatchClause] = field(default_factory=list)
    _where: Optional[WhereClause] = None
    _with_clause: Optional[str] = None
    _return: Optional[ReturnClause] = None
    _parameters: Dict[str, Any] = field(default_factory=dict)
    _unwind: Optional[str] = None
    _delete: Optional[str] = None
    _set_clauses: List[str] = field(default_factory=list)
    _merge: Optional[str] = None
    _create: Optional[str] = None

    def match(self, pattern: str, **variables: str) -> CypherBuilder:
        """Add a MATCH clause."""
        self._matches.append(MatchClause(pattern=pattern, variables=variables))
        return self

    def optional_match(
        self, pattern: str, **variables: str
    ) -> CypherBuilder:
        """Add an OPTIONAL MATCH clause."""
        self._matches.append(
            MatchClause(pattern=pattern, optional=True, variables=variables)
        )
        return self

    def where(
        self, condition: str, **parameters: Any
    ) -> CypherBuilder:
        """Add a WHERE condition."""
        if self._where is None:
            self._where = WhereClause()

        self._where.conditions.append(condition)
        self._where.parameters.update(parameters)
        return self

    def and_where(
        self, condition: str, **parameters: Any
    ) -> CypherBuilder:
        """Add an AND condition to WHERE."""
        if self._where is None:
            self._where = WhereClause()

        self._where.conditions.append(f"AND {condition}")
        self._where.parameters.update(parameters)
        return self

    def or_where(
        self, condition: str, **parameters: Any
    ) -> CypherBuilder:
        """Add an OR condition to WHERE."""
        if self._where is None:
            self._where = WhereClause()

        self._where.conditions.append(f"OR {condition}")
        self._where.parameters.update(parameters)
        return self

    def with_expr(self, expressions: str) -> CypherBuilder:
        """Add a WITH clause."""
        self._with_clause = expressions
        return self

    def unwind(self, expression: str, variable: str) -> CypherBuilder:
        """Add an UNWIND clause."""
        self._unwind = f"UNWIND {expression} AS {variable}"
        return self

    def return_expr(self, *expressions: str) -> CypherBuilder:
        """Add a RETURN clause."""
        if self._return is None:
            self._return = ReturnClause()

        self._return.expressions.extend(expressions)
        return self

    def return_distinct(self, *expressions: str) -> CypherBuilder:
        """Add a RETURN DISTINCT clause."""
        self.return_expr(*expressions)
        self._return.distinct = True
        return self

    def order_by(self, order: str) -> CypherBuilder:
        """Add ORDER BY clause."""
        if self._return is None:
            self._return = ReturnClause()
        self._return.order_by = order
        return self

    def skip(self, count: int) -> CypherBuilder:
        """Add SKIP clause."""
        if self._return is None:
            self._return = ReturnClause()
        self._return.skip = count
        return self

    def limit(self, count: int) -> CypherBuilder:
        """Add LIMIT clause."""
        if self._return is None:
            self._return = ReturnClause()
        self._return.limit = count
        return self

    def set(self, property_set: str) -> CypherBuilder:
        """Add a SET clause."""
        self._set_clauses.append(f"SET {property_set}")
        return self

    def merge(
        self, pattern: str, on_create: Optional[str] = None
    ) -> CypherBuilder:
        """Add a MERGE clause with optional ON CREATE."""
        self._merge = pattern
        if on_create:
            self._merge += f" ON CREATE {on_create}"
        return self

    def create(self, pattern: str) -> CypherBuilder:
        """Add a CREATE clause."""
        self._create = pattern
        return self

    def delete(self, pattern: str, detach: bool = False) -> CypherBuilder:
        """Add a DELETE clause."""
        prefix = "DETACH " if detach else ""
        self._delete = f"{prefix}DELETE {pattern}"
        return self

    def param(self, name: str, value: Any) -> CypherBuilder:
        """Add a query parameter."""
        self._parameters[name] = value
        return self

    def params(self, **kwargs: Any) -> CypherBuilder:
        """Add multiple query parameters."""
        self._parameters.update(kwargs)
        return self

    def build(self) -> Tuple[str, Dict[str, Any]]:
        """
        Build the Cypher query.

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        parts = []

        # MATCH clauses
        for match in self._matches:
            prefix = "OPTIONAL " if match.optional else ""
            parts.append(f"{prefix}MATCH {match.pattern}")

        # UNWIND
        if self._unwind:
            parts.append(self._unwind)

        # MERGE
        if self._merge:
            parts.append(f"MERGE {self._merge}")

        # CREATE
        if self._create:
            parts.append(f"CREATE {self._create}")

        # WHERE
        if self._where and self._where.conditions:
            where_str = " WHERE " + " ".join(self._where.conditions)
            parts.append(where_str)

        # WITH
        if self._with_clause:
            parts.append(f"WITH {self._with_clause}")

        # SET
        for set_clause in self._set_clauses:
            parts.append(set_clause)

        # DELETE
        if self._delete:
            parts.append(self._delete)

        # RETURN
        if self._return:
            distinct = "DISTINCT " if self._return.distinct else ""
            return_expr = ", ".join(self._return.expressions)
            return_str = f"RETURN {distinct}{return_expr}"

            if self._return.order_by:
                return_str += f" ORDER BY {self._return.order_by}"
            if self._return.skip is not None:
                return_str += f" SKIP {self._return.skip}"
            if self._return.limit is not None:
                return_str += f" LIMIT {self._return.limit}"

            parts.append(return_str)

        query = "\n".join(parts)
        all_params = {**self._parameters}
        if self._where:
            all_params.update(self._where.parameters)

        return query, all_params


# ==================== Query Templates ====================


class CypherTemplates:
    """
    Pre-built Cypher query templates for common PilotSuite patterns.
    """

    @staticmethod
    def find_entity(entity_id: str) -> Tuple[str, Dict[str, Any]]:
        """Find a specific entity by ID."""
        return (
            """
            MATCH (n:Entity {id: $entity_id})
            RETURN n
            """,
            {"entity_id": entity_id},
        )

    @staticmethod
    def find_entity_with_relationships(
        entity_id: str, max_hops: int = 2
    ) -> Tuple[str, Dict[str, Any]]:
        """Find an entity and its relationships."""
        return (
            f"""
            MATCH (n:Entity {{id: $entity_id}})
            OPTIONAL MATCH (n)-[r*1..{max_hops}]-(neighbor)
            RETURN n, r, neighbor
            LIMIT $limit
            """,
            {"entity_id": entity_id, "limit": 500},
        )

    @staticmethod
    def find_entities_by_domain(
        domain: str, limit: int = 100
    ) -> Tuple[str, Dict[str, Any]]:
        """Find all entities in a domain."""
        return (
            """
            MATCH (n:Entity {domain: $domain})
            RETURN n
            ORDER BY n.label
            LIMIT $limit
            """,
            {"domain": domain, "limit": limit},
        )

    @staticmethod
    def find_entities_by_area(
        area_id: str, limit: int = 100
    ) -> Tuple[str, Dict[str, Any]]:
        """Find all entities in an area."""
        return (
            """
            MATCH (n:Entity)-[:BELONGS_TO]->(a:Area {id: $area_id})
            RETURN n
            ORDER BY n.label
            LIMIT $limit
            """,
            {"area_id": area_id, "limit": limit},
        )

    @staticmethod
    def find_path_between(
        source_id: str, target_id: str, max_depth: int = 5
    ) -> Tuple[str, Dict[str, Any]]:
        """Find paths between two nodes."""
        return (
            f"""
            MATCH (source {{id: $source_id}})
            MATCH (target {{id: $target_id}})
            MATCH path = allShortestPaths((source)-[*1..{max_depth}]-(target))
            RETURN path
            LIMIT $limit
            """,
            {"source_id": source_id, "target_id": target_id, "limit": 10},
        )

    @staticmethod
    def find_patterns_for_entity(
        entity_id: str, min_confidence: float = 0.5
    ) -> Tuple[str, Dict[str, Any]]:
        """Find patterns involving a specific entity."""
        return (
            """
            MATCH (e:Entity {id: $entity_id})
            MATCH (p:Pattern)-[:INVOLVES]->(e)
            WHERE p.confidence >= $min_confidence
            RETURN p, e
            ORDER BY p.confidence DESC
            LIMIT $limit
            """,
            {"entity_id": entity_id, "min_confidence": min_confidence, "limit": 50},
        )

    @staticmethod
    def find_mood_associations(
        mood_id: str, min_weight: float = 0.3
    ) -> Tuple[str, Dict[str, Any]]:
        """Find entities associated with a mood."""
        return (
            """
            MATCH (m:Mood {id: $mood_id})
            MATCH (e:Entity)-[r:RELATES_TO_MOOD]->(m)
            WHERE r.weight >= $min_weight
            RETURN e, r
            ORDER BY r.weight DESC
            LIMIT $limit
            """,
            {"mood_id": mood_id, "min_weight": min_weight, "limit": 50},
        )

    @staticmethod
    def get_zone_summary(zone_id: str) -> Tuple[str, Dict[str, Any]]:
        """Get summary of a zone including areas and entities."""
        return (
            """
            MATCH (z:Zone {id: $zone_id})
            OPTIONAL MATCH (z)-[:CONTAINS]->(a:Area)
            OPTIONAL MATCH (a)<-[:BELONGS_TO]-(e:Entity)
            RETURN
              z,
              collect(DISTINCT a) AS areas,
              collect(DISTINCT e) AS entities
            """,
            {"zone_id": zone_id},
        )

    @staticmethod
    def get_graph_stats() -> Tuple[str, Dict[str, Any]]:
        """Get graph statistics."""
        return (
            """
            MATCH (n)
            OPTIONAL MATCH ()-[r]->()
            WITH
              count(DISTINCT n) AS node_count,
              count(DISTINCT r) AS edge_count,
              count(DISTINCT labels(n)) AS label_count
            RETURN node_count, edge_count, label_count
            """,
            {},
        )

    @staticmethod
    def get_node_degree_distribution(
        top_k: int = 20
    ) -> Tuple[str, Dict[str, Any]]:
        """Get node degree distribution."""
        return (
            """
            MATCH (n)
            WITH n, size((n)--()) AS degree
            RETURN n.id AS id, n.label AS label, labels(n)[0] AS type, degree
            ORDER BY degree DESC
            LIMIT $top_k
            """,
            {"top_k": top_k},
        )

    @staticmethod
    def find_orphan_nodes() -> Tuple[str, Dict[str, Any]]:
        """Find nodes with no relationships."""
        return (
            """
            MATCH (n)
            WHERE NOT (n)--()
            RETURN n
            LIMIT $limit
            """,
            {"limit": 100},
        )

    @staticmethod
    def cleanup_orphan_nodes() -> Tuple[str, Dict[str, Any]]:
        """Delete orphan nodes."""
        return (
            """
            MATCH (n)
            WHERE NOT (n)--()
            DETACH DELETE n
            """,
            {},
        )

    @staticmethod
    def find_similar_entities(
        entity_id: str, limit: int = 10
    ) -> Tuple[str, Dict[str, Any]]:
        """Find entities similar to a given entity (same domain/area)."""
        return (
            """
            MATCH (source:Entity {id: $entity_id})
            MATCH (target:Entity)
            WHERE target.id <> source.id
              AND (target.domain = source.domain OR target.area_id = source.area_id)
            RETURN target,
                   CASE
                     WHEN target.domain = source.domain AND target.area_id = source.area_id THEN 2
                     WHEN target.domain = source.domain OR target.area_id = source.area_id THEN 1
                     ELSE 0
                   END AS similarity
            ORDER BY similarity DESC, target.label
            LIMIT $limit
            """,
            {"entity_id": entity_id, "limit": limit},
        )

    @staticmethod
    def get_temporal_patterns(
        time_window_sec: int = 300, min_support: int = 5
    ) -> Tuple[str, Dict[str, Any]]:
        """Get patterns within a time window."""
        return (
            """
            MATCH (p:Pattern)
            WHERE p.time_window_sec <= $time_window_sec
              AND p.support >= $min_support
            RETURN p
            ORDER BY p.confidence DESC, p.support DESC
            LIMIT $limit
            """,
            {
                "time_window_sec": time_window_sec,
                "min_support": min_support,
                "limit": 100,
            },
        )

    @staticmethod
    def export_for_visualization(
        root_id: Optional[str] = None,
        max_nodes: int = 500,
        max_edges: int = 1000,
    ) -> Tuple[str, Dict[str, Any]]:
        """Export graph data for visualization."""
        if root_id:
            return (
                """
                MATCH (root {id: $root_id})
                OPTIONAL MATCH (root)-[r]-(neighbor)
                WITH root, collect(DISTINCT neighbor) AS neighbors
                UNWIND [root] + neighbors AS node
                WITH collect(DISTINCT node) AS nodes
                UNWIND nodes AS n
                MATCH (n)-[rel]-(m)
                WHERE m IN nodes
                RETURN n AS node, rel, m AS other
                LIMIT $max_edges
                """,
                {"root_id": root_id, "max_edges": max_edges},
            )
        else:
            return (
                """
                MATCH (n)
                WITH n LIMIT $max_nodes
                MATCH (n)-[r]-(m)
                WHERE ID(n) < ID(m)
                RETURN n AS node, r, m AS other
                LIMIT $max_edges
                """,
                {"max_nodes": max_nodes, "max_edges": max_edges},
            )


# ==================== Query Validator ====================


class CypherValidator:
    """Validates Cypher queries for safety and correctness."""

    # Dangerous operations that require explicit approval
    DANGEROUS_KEYWORDS = [
        "DETACH DELETE",
        "DELETE",
        "DROP",
        "CREATE CONSTRAINT",
        "DROP CONSTRAINT",
        "CREATE INDEX",
        "DROP INDEX",
    ]

    @staticmethod
    def is_read_only(query: str) -> bool:
        """Check if a query is read-only."""
        query_upper = query.strip().upper()
        write_keywords = [
            "CREATE",
            "MERGE",
            "DELETE",
            "SET",
            "REMOVE",
            "ADD",
            "DROP",
        ]
        return not any(query_upper.startswith(kw) for kw in write_keywords)

    @staticmethod
    def is_safe(query: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a query is safe to execute.

        Returns:
            Tuple of (is_safe, warning_message)
        """
        query_upper = query.upper()

        for keyword in CypherValidator.DANGEROUS_KEYWORDS:
            if keyword in query_upper:
                return (
                    False,
                    f"Query contains dangerous operation: {keyword}",
                )

        # Check for missing LIMIT on unbounded queries
        if "MATCH" in query_upper and "LIMIT" not in query_upper:
            if "RETURN" in query_upper and "count" not in query_upper.lower():
                return (
                    False,
                    "Unbounded query without LIMIT - may return too many results",
                )

        return True, None

    @staticmethod
    def validate_parameters(
        query: str, parameters: Dict[str, Any]
    ) -> List[str]:
        """
        Validate that all query parameters are provided.

        Returns:
            List of missing parameter names.
        """
        import re

        # Find all $param references
        param_pattern = r"\$(\w+)"
        required_params = set(re.findall(param_pattern, query))
        provided_params = set(parameters.keys())

        missing = required_params - provided_params
        return list(missing)


# ==================== Query Optimizer ====================


class CypherOptimizer:
    """Provides query optimization suggestions."""

    @staticmethod
    def suggest_optimizations(query: str) -> List[str]:
        """
        Suggest optimizations for a Cypher query.

        Returns:
            List of optimization suggestions.
        """
        suggestions = []
        query_upper = query.upper()

        # Check for missing indexes hints
        if "MATCH" in query_upper and "USING INDEX" not in query_upper:
            if "{id:" in query or "id =" in query:
                suggestions.append(
                    "Consider adding USING INDEX hint for id lookups"
                )

        # Check for Cartesian products
        if query_upper.count("MATCH") > 1 and "WITH" not in query_upper:
            suggestions.append(
                "Multiple MATCH without WITH may cause Cartesian product"
            )

        # Check for missing labels
        if "MATCH (n)" in query or "MATCH (n," in query:
            suggestions.append(
                "Node pattern without label - add label for better performance"
            )

        # Check for unbounded variable-length paths
        if "*]" in query and "..]" not in query:
            suggestions.append(
                "Unbounded variable-length path - add max depth with ..N"
            )

        return suggestions
