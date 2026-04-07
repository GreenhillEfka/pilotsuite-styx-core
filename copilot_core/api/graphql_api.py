"""P5-003: GraphQL API — Schema, Resolvers, Subscriptions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class GraphQLType(Enum):
    """GraphQL scalar types."""
    STRING = "String"
    INT = "Int"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    ID = "ID"


@dataclass
class GraphQLField:
    """GraphQL field definition."""
    name: str
    type: str
    args: Optional[Dict[str, str]] = None
    description: Optional[str] = None


@dataclass
class GraphQLType:
    """GraphQL type definition."""
    name: str
    fields: List[GraphQLField] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class GraphQLQuery:
    """GraphQL query definition."""
    name: str
    args: Dict[str, str]
    return_type: str
    resolver: Callable
    description: Optional[str] = None


@dataclass
class GraphQLMutation:
    """GraphQL mutation definition."""
    name: str
    args: Dict[str, str]
    return_type: str
    resolver: Callable
    description: Optional[str] = None


class GraphQLAPI:
    """GraphQL API with schema and resolvers."""

    def __init__(self):
        self._types: Dict[str, GraphQLType] = {}
        self._queries: Dict[str, GraphQLQuery] = {}
        self._mutations: Dict[str, GraphQLMutation] = {}
        self._subscriptions: Dict[str, Callable] = {}
        
        self._register_core_types()
        self._register_core_queries()
        self._register_core_mutations()

    def _register_core_types(self):
        """Register core GraphQL types."""
        # User type
        self._types["User"] = GraphQLType(
            name="User",
            fields=[
                GraphQLField("id", "ID!"),
                GraphQLField("name", "String"),
                GraphQLField("preferences", "[Preference]"),
            ]
        )
        
        # Preference type
        self._types["Preference"] = GraphQLType(
            name="Preference",
            fields=[
                GraphQLField("id", "ID!"),
                GraphQLField("category", "String!"),
                GraphQLField("key", "String!"),
                GraphQLField("value", "String!"),
            ]
        )
        
        # Device type
        self._types["Device"] = GraphQLType(
            name="Device",
            fields=[
                GraphQLField("id", "ID!"),
                GraphQLField("name", "String!"),
                GraphQLField("type", "String!"),
                GraphQLField("state", "String"),
            ]
        )
        
        # Pattern type
        self._types["Pattern"] = GraphQLType(
            name="Pattern",
            fields=[
                GraphQLField("id", "ID!"),
                GraphQLField("type", "String!"),
                GraphQLField("description", "String!"),
                GraphQLField("confidence", "Float!"),
            ]
        )

    def _register_core_queries(self):
        """Register core queries."""
        self._queries["health"] = GraphQLQuery(
            name="health",
            args={},
            return_type="HealthStatus!",
            resolver=lambda: {"status": "healthy"},
            description="Check system health"
        )
        
        self._queries["user"] = GraphQLQuery(
            name="user",
            args={"id": "ID!"},
            return_type="User",
            resolver=lambda id: {"id": id, "name": "User"},
            description="Get user by ID"
        )
        
        self._queries["users"] = GraphQLQuery(
            name="users",
            args={},
            return_type="[User!]!",
            resolver=lambda: [],
            description="List all users"
        )
        
        self._queries["devices"] = GraphQLQuery(
            name="devices",
            args={"type": "String"},
            return_type="[Device!]!",
            resolver=lambda type=None: [],
            description="List devices"
        )
        
        self._queries["patterns"] = GraphQLQuery(
            name="patterns",
            args={},
            return_type="[Pattern!]!",
            resolver=lambda: [],
            description="Get detected patterns"
        )

    def _register_core_mutations(self):
        """Register core mutations."""
        self._mutations["setPreference"] = GraphQLMutation(
            name="setPreference",
            args={"userId": "ID!", "category": "String!", "key": "String!", "value": "String!"},
            return_type="Preference!",
            resolver=lambda userId, category, key, value: {"id": "1", "category": category, "key": key, "value": value},
            description="Set user preference"
        )
        
        self._mutations["executeAction"] = GraphQLMutation(
            name="executeAction",
            args={"deviceId": "ID!", "action": "String!"},
            return_type="Boolean!",
            resolver=lambda deviceId, action: True,
            description="Execute device action"
        )

    def register_query(self, query: GraphQLQuery):
        """Register a custom query."""
        self._queries[query.name] = query

    def register_mutation(self, mutation: GraphQLMutation):
        """Register a custom mutation."""
        self._mutations[mutation.name] = mutation

    def get_schema(self) -> str:
        """Generate GraphQL schema SDL."""
        lines = []
        
        # Types
        for type_def in self._types.values():
            lines.append(f"# {type_def.description or ''}")
            lines.append(f"type {type_def.name} {{")
            for field in type_def.fields:
                lines.append(f"  {field.name}: {field.type}")
            lines.append("}")
            lines.append("")
        
        # Queries
        lines.append("type Query {")
        for query in self._queries.values():
            args = ", ".join(f"{k}: {v}" for k, v in query.args.items())
            if args:
                lines.append(f"  # {query.description or ''}")
                lines.append(f"  {query.name}({args}): {query.return_type}")
            else:
                lines.append(f"  # {query.description or ''}")
                lines.append(f"  {query.name}: {query.return_type}")
        lines.append("}")
        lines.append("")
        
        # Mutations
        lines.append("type Mutation {")
        for mutation in self._mutations.values():
            args = ", ".join(f"{k}: {v}" for k, v in mutation.args.items())
            lines.append(f"  # {mutation.description or ''}")
            lines.append(f"  {mutation.name}({args}): {mutation.return_type}")
        lines.append("}")
        
        return "\n".join(lines)

    def save_schema(self, path: str):
        """Save schema to file."""
        schema = self.get_schema()
        with open(path, 'w') as f:
            f.write(schema)
        logger.info(f"Saved GraphQL schema to {path}")

    def execute(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        # Simplified execution (would use graphql-core)
        return {
            "data": {},
            "errors": None
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get GraphQL API statistics."""
        return {
            "types": len(self._types),
            "queries": len(self._queries),
            "mutations": len(self._mutations),
            "subscriptions": len(self._subscriptions),
        }


# Global default GraphQL API
default_graphql_api: Optional[GraphQLAPI] = None


def init_graphql_api() -> GraphQLAPI:
    """Initialize global GraphQL API."""
    global default_graphql_api
    default_graphql_api = GraphQLAPI()
    return default_graphql_api
