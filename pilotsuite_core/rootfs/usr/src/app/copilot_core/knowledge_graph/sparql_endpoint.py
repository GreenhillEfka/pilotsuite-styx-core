"""SPARQL Query Interface for PilotSuite Knowledge Graph.

Provides SPARQL 1.1 SELECT query parsing and execution against the knowledge graph.
Supports basic graph patterns (subject/predicate/object) with query validation
and DoS prevention.

Endpoint: POST /api/v1/knowledge/sparql
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import Edge, EdgeType, Node, NodeType
from .graph_store import get_graph_store

_LOGGER = logging.getLogger(__name__)

# Query complexity limits for DoS prevention
MAX_QUERY_LENGTH = 4096  # Maximum SPARQL query string length
MAX_RESULTS = 1000  # Maximum results returned
MAX_HOPS = 3  # Maximum traversal depth
DEFAULT_LIMIT = 100  # Default result limit


@dataclass
class SPARQLQuery:
    """Parsed SPARQL SELECT query."""
    variables: list[str] = field(default_factory=list)
    patterns: list[TriplePattern] = field(default_factory=list)
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    filters: list[Filter] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    distinct: bool = False


@dataclass
class TriplePattern:
    """A triple pattern (subject, predicate, object)."""
    subject: str
    predicate: str
    obj: str  # 'obj' to avoid keyword conflict
    
    def is_variable(self, term: str) -> bool:
        """Check if a term is a variable (starts with ?)."""
        return term.startswith("?")
    
    def get_variables(self) -> list[str]:
        """Return all variables in this pattern."""
        vars = []
        if self.is_variable(self.subject):
            vars.append(self.subject)
        if self.is_variable(self.predicate):
            vars.append(self.predicate)
        if self.is_variable(self.obj):
            vars.append(self.obj)
        return vars


@dataclass
class Filter:
    """A FILTER clause."""
    expression: str
    variable: str


class SPARQLParser:
    """Basic SPARQL 1.1 SELECT query parser."""
    
    # Regex patterns for parsing
    PREFIX_PATTERN = re.compile(r'PREFIX\s+(\w+):\s*<([^>]+)>', re.IGNORECASE)
    SELECT_PATTERN = re.compile(r'SELECT\s+(DISTINCT\s+)?(.+?)\s+WHERE', re.IGNORECASE | re.DOTALL)
    WHERE_PATTERN = re.compile(r'WHERE\s*\{(.+?)\}', re.IGNORECASE | re.DOTALL)
    TRIPLE_PATTERN = re.compile(r'(\?[\w]+|<[^>]+>|[\w:]+)\s+(\?[\w]+|<[^>]+>|[\w:]+)\s+(\?[\w]+|<[^>]+>|[\w:]+)\s*\.?', re.IGNORECASE)
    LIMIT_PATTERN = re.compile(r'LIMIT\s+(\d+)', re.IGNORECASE)
    OFFSET_PATTERN = re.compile(r'OFFSET\s+(\d+)', re.IGNORECASE)
    ORDER_BY_PATTERN = re.compile(r'ORDER\s+BY\s+(.+?)(?:LIMIT|OFFSET|$)', re.IGNORECASE | re.DOTALL)
    FILTER_PATTERN = re.compile(r'FILTER\s*\(([^)]+)\)', re.IGNORECASE)
    VARIABLE_PATTERN = re.compile(r'\?(\w+)')
    
    def parse(self, query: str) -> SPARQLQuery:
        """Parse a SPARQL SELECT query string.
        
        Args:
            query: SPARQL query string
            
        Returns:
            Parsed SPARQLQuery object
            
        Raises:
            ValueError: If query is invalid or unsupported
        """
        # Validate query length
        if len(query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query too long: {len(query)} > {MAX_QUERY_LENGTH} characters")
        
        query = query.strip()
        
        # Extract prefixes (stored but not used in basic implementation)
        prefixes = dict(self.PREFIX_PATTERN.findall(query))
        
        # Parse SELECT clause
        select_match = self.SELECT_PATTERN.search(query)
        if not select_match:
            raise ValueError("Invalid SPARQL: missing SELECT clause")
        
        distinct = bool(select_match.group(1))
        select_vars = select_match.group(2).strip()
        
        # Parse variables
        if select_vars == "*":
            variables = ["*"]
        else:
            variables = self.VARIABLE_PATTERN.findall(select_vars)
            variables = [f"?{v}" for v in variables]
        
        # Parse WHERE clause
        where_match = self.WHERE_PATTERN.search(query)
        if not where_match:
            raise ValueError("Invalid SPARQL: missing WHERE clause")
        
        where_content = where_match.group(1)
        
        # Parse triple patterns
        patterns = []
        for match in self.TRIPLE_PATTERN.finditer(where_content):
            patterns.append(TriplePattern(
                subject=match.group(1).strip("<>"),
                predicate=match.group(2).strip("<>"),
                obj=match.group(3).strip("<>")
            ))
        
        if not patterns:
            raise ValueError("Invalid SPARQL: no triple patterns found")
        
        # Parse LIMIT
        limit = DEFAULT_LIMIT
        limit_match = self.LIMIT_PATTERN.search(query)
        if limit_match:
            limit = min(int(limit_match.group(1)), MAX_RESULTS)
        
        # Parse OFFSET
        offset = 0
        offset_match = self.OFFSET_PATTERN.search(query)
        if offset_match:
            offset = int(offset_match.group(1))
        
        # Parse ORDER BY
        order_by = []
        order_match = self.ORDER_BY_PATTERN.search(query)
        if order_match:
            order_by = self.VARIABLE_PATTERN.findall(order_match.group(1))
            order_by = [f"?{v}" for v in order_by]
        
        # Parse FILTER clauses
        filters = []
        for match in self.FILTER_PATTERN.finditer(where_content):
            expr = match.group(1).strip()
            # Extract variable from filter expression
            var_match = self.VARIABLE_PATTERN.search(expr)
            if var_match:
                filters.append(Filter(expression=expr, variable=f"?{var_match.group(1)}"))
        
        return SPARQLQuery(
            variables=variables if variables else ["*"],
            patterns=patterns,
            limit=limit,
            offset=offset,
            filters=filters,
            order_by=order_by,
            distinct=distinct
        )


class SPARQLExecutor:
    """Execute SPARQL queries against the knowledge graph."""
    
    def __init__(self, graph_store=None):
        """Initialize the executor.
        
        Args:
            graph_store: GraphStore instance (uses singleton if None)
        """
        self.store = graph_store or get_graph_store()
    
    def execute(self, query: SPARQLQuery) -> dict[str, Any]:
        """Execute a parsed SPARQL query.
        
        Args:
            query: Parsed SPARQLQuery object
            
        Returns:
            Query results as dict with 'results' and 'count' keys
        """
        _LOGGER.debug("Executing SPARQL query with %d patterns", len(query.patterns))
        
        # Execute query patterns
        bindings = self._execute_patterns(query.patterns)
        
        # Apply filters
        if query.filters:
            bindings = self._apply_filters(bindings, query.filters)
        
        # Apply ordering
        if query.order_by:
            bindings = self._apply_order(bindings, query.order_by)
        
        # Apply offset and limit
        start = query.offset
        end = start + query.limit
        bindings = bindings[start:end]
        
        # Project variables
        if query.variables != ["*"]:
            bindings = self._project_variables(bindings, query.variables)
        
        # Remove duplicates if DISTINCT
        if query.distinct:
            seen = set()
            unique = []
            for b in bindings:
                key = tuple(sorted(b.items()))
                if key not in seen:
                    seen.add(key)
                    unique.append(b)
            bindings = unique
        
        return {
            "results": bindings,
            "count": len(bindings),
        }
    
    def _execute_patterns(self, patterns: list[TriplePattern]) -> list[dict[str, Any]]:
        """Execute triple patterns and return variable bindings.
        
        Args:
            patterns: List of triple patterns
            
        Returns:
            List of variable binding dictionaries
        """
        if not patterns:
            return []
        
        # Start with first pattern
        first = patterns[0]
        bindings = self._match_pattern(first)
        
        # Join with remaining patterns
        for pattern in patterns[1:]:
            bindings = self._join_bindings(bindings, pattern)
        
        return bindings
    
    def _match_pattern(self, pattern: TriplePattern) -> list[dict[str, Any]]:
        """Match a single triple pattern against the graph.
        
        Args:
            pattern: Triple pattern to match
            
        Returns:
            List of variable bindings
        """
        results = []
        
        # Determine what we're looking for
        subject_is_var = pattern.is_variable(pattern.subject)
        predicate_is_var = pattern.is_variable(pattern.predicate)
        obj_is_var = pattern.is_variable(pattern.obj)
        
        # Get all nodes and edges for matching
        all_nodes = []
        all_edges = []
        
        # Fetch nodes (limited for safety)
        for node_type in NodeType:
            nodes = self.store.get_nodes_by_type(node_type, limit=500)
            all_nodes.extend(nodes)
        
        # For edge matching, we need to search from various starting points
        # This is a simplified approach - production would use indexed queries
        
        # Match based on pattern specificity
        if not subject_is_var and not predicate_is_var and not obj_is_var:
            # Fully grounded triple - check if it exists
            node = self.store.get_node(pattern.subject)
            if node:
                edges = self.store.get_edges_from(pattern.subject)
                for edge in edges:
                    if edge.target == pattern.obj:
                        results.append({})
                        break
        
        elif subject_is_var and predicate_is_var and obj_is_var:
            # All variables - return all triples (limited)
            for node in all_nodes[:100]:
                edges = self.store.get_edges_from(node.id)
                for edge in edges[:10]:
                    results.append({
                        pattern.subject: node.id,
                        pattern.predicate: edge.type.value,
                        pattern.obj: edge.target,
                    })
        
        elif not subject_is_var and predicate_is_var and obj_is_var:
            # Subject is grounded
            node = self.store.get_node(pattern.subject)
            if node:
                edges = self.store.get_edges_from(pattern.subject)
                for edge in edges:
                    results.append({
                        pattern.predicate: edge.type.value,
                        pattern.obj: edge.target,
                    })
        
        elif subject_is_var and not predicate_is_var and obj_is_var:
            # Predicate is grounded (edge type)
            try:
                edge_type = EdgeType(pattern.predicate)
                # Search for edges of this type
                for node in all_nodes:
                    edges = self.store.get_edges_from(node.id, edge_type)
                    for edge in edges:
                        results.append({
                            pattern.subject: node.id,
                            pattern.obj: edge.target,
                        })
            except ValueError:
                pass  # Invalid edge type
        
        elif subject_is_var and predicate_is_var and not obj_is_var:
            # Object is grounded
            # Find edges pointing to this object
            for node in all_nodes:
                edges = self.store.get_edges_to(pattern.obj)
                for edge in edges:
                    if edge.source == node.id:
                        results.append({
                            pattern.subject: node.id,
                            pattern.predicate: edge.type.value,
                        })
        
        elif not subject_is_var and not predicate_is_var and obj_is_var:
            # Subject and predicate grounded
            node = self.store.get_node(pattern.subject)
            if node:
                try:
                    edge_type = EdgeType(pattern.predicate)
                    edges = self.store.get_edges_from(pattern.subject, edge_type)
                    for edge in edges:
                        results.append({
                            pattern.obj: edge.target,
                        })
                except ValueError:
                    pass
        
        elif not subject_is_var and obj_is_var and predicate_is_var:
            # Subject and object grounded, predicate variable
            node = self.store.get_node(pattern.subject)
            if node:
                edges = self.store.get_edges_from(pattern.subject)
                for edge in edges:
                    if edge.target == pattern.obj:
                        results.append({
                            pattern.predicate: edge.type.value,
                        })
        
        elif subject_is_var and not predicate_is_var and not obj_is_var:
            # Predicate and object grounded
            try:
                edge_type = EdgeType(pattern.predicate)
                edges = self.store.get_edges_to(pattern.obj, edge_type)
                for edge in edges:
                    results.append({
                        pattern.subject: edge.source,
                    })
            except ValueError:
                pass
        
        return results
    
    def _join_bindings(self, bindings: list[dict[str, Any]], pattern: TriplePattern) -> list[dict[str, Any]]:
        """Join existing bindings with a new pattern.
        
        Args:
            bindings: Current variable bindings
            pattern: Next pattern to match
            
        Returns:
            Updated bindings
        """
        if not bindings:
            return self._match_pattern(pattern)
        
        results = []
        for binding in bindings:
            # Substitute known values into pattern
            subject = binding.get(pattern.subject, pattern.subject)
            predicate = binding.get(pattern.predicate, pattern.predicate)
            obj = binding.get(pattern.obj, pattern.obj)
            
            # Create new pattern with substituted values
            new_pattern = TriplePattern(
                subject=subject if not pattern.is_variable(subject) else pattern.subject,
                predicate=predicate if not pattern.is_variable(predicate) else pattern.predicate,
                obj=obj if not pattern.is_variable(obj) else pattern.obj
            )
            
            # Match and extend bindings
            matches = self._match_pattern(new_pattern)
            for match in matches:
                extended = {**binding, **match}
                results.append(extended)
        
        return results
    
    def _apply_filters(self, bindings: list[dict[str, Any]], filters: list[Filter]) -> list[dict[str, Any]]:
        """Apply FILTER clauses to bindings.
        
        Args:
            bindings: Variable bindings
            filters: Filter expressions
            
        Returns:
            Filtered bindings
        """
        results = []
        for binding in bindings:
            keep = True
            for f in filters:
                var_value = binding.get(f.variable)
                if var_value is None:
                    keep = False
                    break
                # Basic filter evaluation (supports: =, !=, <, >, <=, >=, CONTAINS, STRSTARTS)
                expr = f.expression
                # Replace variable with value
                expr = expr.replace(f.variable, repr(str(var_value)))
                try:
                    # Safe evaluation of simple expressions
                    if "CONTAINS" in expr.upper():
                        # Handle CONTAINS(str, substr)
                        match = re.search(r'CONTAINS\(([^,]+),\s*([^)]+)\)', expr, re.IGNORECASE)
                        if match:
                            str_val = match.group(1).strip("'\"")
                            substr = match.group(2).strip("'\"")
                            keep = substr in str_val
                    elif "STRSTARTS" in expr.upper():
                        # Handle STRSTARTS(str, prefix)
                        match = re.search(r'STRSTARTS\(([^,]+),\s*([^)]+)\)', expr, re.IGNORECASE)
                        if match:
                            str_val = match.group(1).strip("'\"")
                            prefix = match.group(2).strip("'\"")
                            keep = str_val.startswith(prefix)
                    else:
                        # Simple comparison
                        keep = eval(expr, {"__builtins__": {}}, {})
                except Exception:
                    keep = False
                if not keep:
                    break
            if keep:
                results.append(binding)
        return results
    
    def _apply_order(self, bindings: list[dict[str, Any]], order_by: list[str]) -> list[dict[str, Any]]:
        """Apply ORDER BY to bindings.
        
        Args:
            bindings: Variable bindings
            order_by: Variables to order by
            
        Returns:
            Ordered bindings
        """
        if not order_by:
            return bindings
        
        def sort_key(binding):
            values = []
            for var in order_by:
                val = binding.get(var, "")
                # Try numeric sort
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = str(val)
                values.append(val)
            return tuple(values)
        
        return sorted(bindings, key=sort_key)
    
    def _project_variables(self, bindings: list[dict[str, Any]], variables: list[str]) -> list[dict[str, Any]]:
        """Project only requested variables.
        
        Args:
            bindings: Variable bindings
            variables: Variables to project
            
        Returns:
            Projected bindings
        """
        results = []
        for binding in bindings:
            projected = {var: binding.get(var) for var in variables if var in binding}
            if projected:
                results.append(projected)
        return results


def validate_sparql_query(query: str) -> tuple[bool, str]:
    """Validate a SPARQL query string.
    
    Args:
        query: SPARQL query string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check length
    if len(query) > MAX_QUERY_LENGTH:
        return False, f"Query too long: {len(query)} > {MAX_QUERY_LENGTH} characters"
    
    # Check for dangerous patterns (basic sanitization)
    dangerous_patterns = [
        r'DELETE\s+DATA',
        r'INSERT\s+DATA',
        r'LOAD\s+<',
        r'CLEAR\s+',
        r'DROP\s+',
        r'CREATE\s+',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return False, f"Query contains unsupported operation: {pattern}"
    
    # Check for SELECT query
    if not re.search(r'SELECT\s+.+WHERE', query, re.IGNORECASE | re.DOTALL):
        return False, "Only SELECT queries are supported"
    
    return True, ""


def execute_sparql(query: str) -> dict[str, Any]:
    """Execute a SPARQL query string.
    
    Args:
        query: SPARQL query string
        
    Returns:
        Query results
        
    Raises:
        ValueError: If query is invalid
    """
    # Validate
    is_valid, error = validate_sparql_query(query)
    if not is_valid:
        raise ValueError(error)
    
    # Parse
    parser = SPARQLParser()
    parsed = parser.parse(query)
    
    # Execute
    executor = SPARQLExecutor()
    return executor.execute(parsed)


# Flask Blueprint for SPARQL endpoint
from flask import Blueprint, jsonify, request

sparql_bp = Blueprint("sparql", __name__, url_prefix="/api/v1/knowledge")


@sparql_bp.post("/sparql")
def sparql_query():
    """Execute a SPARQL query against the knowledge graph.
    
    Request body:
        {
            "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
        }
    
    Returns:
        {
            "ok": true,
            "results": [...],
            "count": N
        }
    """
    try:
        data = request.get_json() or {}
        query = data.get("query", "")
        
        if not query:
            return jsonify({
                "ok": False,
                "error": "Missing 'query' field in request body",
            }), 400
        
        # Validate query
        is_valid, error = validate_sparql_query(query)
        if not is_valid:
            return jsonify({
                "ok": False,
                "error": error,
            }), 400
        
        # Execute query
        result = execute_sparql(query)
        
        return jsonify({
            "ok": True,
            **result,
        })
    
    except ValueError as e:
        _LOGGER.warning("Invalid SPARQL query: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
        }), 400
    
    except Exception as e:
        _LOGGER.exception("SPARQL query execution failed")
        return jsonify({
            "ok": False,
            "error": f"Query execution failed: {str(e)}",
        }), 500


@sparql_bp.get("/sparql/help")
def sparql_help():
    """Return SPARQL endpoint documentation."""
    return jsonify({
        "ok": True,
        "endpoint": "/api/v1/knowledge/sparql",
        "method": "POST",
        "supported": "SPARQL 1.1 SELECT queries",
        "example": {
            "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
        },
        "limits": {
            "max_query_length": MAX_QUERY_LENGTH,
            "max_results": MAX_RESULTS,
            "default_limit": DEFAULT_LIMIT,
        },
        "features": [
            "Basic graph patterns (subject/predicate/object)",
            "FILTER clauses (CONTAINS, STRSTARTS, comparisons)",
            "ORDER BY",
            "LIMIT and OFFSET",
            "DISTINCT",
        ],
    })
