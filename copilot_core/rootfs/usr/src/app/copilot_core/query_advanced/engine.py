"""Query Engine Advanced — Slice 64.

Advanced query engine for PilotSuite Core.

Features:
- SQL-like query parsing
- Filter expressions
- Sorting and pagination
- Aggregation functions
- Query optimization hints
- Result caching
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Set, Tuple, Union
from enum import Enum
import uuid
import operator

logger = logging.getLogger(__name__)


class Operator(Enum):
    """Query operators."""
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    IN = "in"
    NIN = "nin"
    LIKE = "like"
    CONTAINS = "contains"
    EXISTS = "exists"
    AND = "and"
    OR = "or"
    NOT = "not"


class SortOrder(Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


class AggregateFunction(Enum):
    """Aggregation functions."""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


@dataclass
class QueryCondition:
    """Query condition."""
    field: str
    operator: Operator
    value: Any
    
    def evaluate(self, item: Dict[str, Any]) -> bool:
        """Evaluate condition against item."""
        field_value = self._get_field_value(item, self.field)
        
        if self.operator == Operator.EQ:
            return field_value == self.value
        elif self.operator == Operator.NE:
            return field_value != self.value
        elif self.operator == Operator.LT:
            return field_value < self.value
        elif self.operator == Operator.LE:
            return field_value <= self.value
        elif self.operator == Operator.GT:
            return field_value > self.value
        elif self.operator == Operator.GE:
            return field_value >= self.value
        elif self.operator == Operator.IN:
            return field_value in self.value
        elif self.operator == Operator.NIN:
            return field_value not in self.value
        elif self.operator == Operator.LIKE:
            pattern = self.value.replace("%", ".*").replace("_", ".")
            return bool(re.match(pattern, str(field_value), re.IGNORECASE))
        elif self.operator == Operator.CONTAINS:
            return self.value in str(field_value)
        elif self.operator == Operator.EXISTS:
            return field_value is not None if self.value else field_value is None
        
        return False
    
    def _get_field_value(self, item: Dict[str, Any], field_path: str) -> Any:
        """Get nested field value."""
        parts = field_path.split(".")
        value = item
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value


@dataclass
class QueryFilter:
    """Query filter with logical operators."""
    conditions: List[QueryCondition] = field(default_factory=list)
    logical_op: Operator = Operator.AND
    
    def evaluate(self, item: Dict[str, Any]) -> bool:
        """Evaluate filter against item."""
        if not self.conditions:
            return True
        
        results = [cond.evaluate(item) for cond in self.conditions]
        
        if self.logical_op == Operator.AND:
            return all(results)
        elif self.logical_op == Operator.OR:
            return any(results)
        
        return False


@dataclass
class SortField:
    """Sort field specification."""
    field: str
    order: SortOrder = SortOrder.ASC


@dataclass
class AggregateSpec:
    """Aggregation specification."""
    function: AggregateFunction
    field: str
    alias: Optional[str] = None


@dataclass
class Query:
    """Query definition."""
    query_id: str
    collection: str
    filter: QueryFilter = field(default_factory=QueryFilter)
    sort: List[SortField] = field(default_factory=list)
    limit: int = 100
    offset: int = 0
    select: List[str] = field(default_factory=list)
    aggregates: List[AggregateSpec] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "collection": self.collection,
            "filter": {
                "conditions": [
                    {"field": c.field, "operator": c.operator.value, "value": c.value}
                    for c in self.filter.conditions
                ],
                "logical_op": self.filter.logical_op.value,
            },
            "sort": [{"field": s.field, "order": s.order.value} for s in self.sort],
            "limit": self.limit,
            "offset": self.offset,
            "select": self.select,
            "aggregates": [
                {"function": a.function.value, "field": a.field, "alias": a.alias}
                for a in self.aggregates
            ],
            "created_at": self.created_at,
        }


@dataclass
class QueryResult:
    """Query result."""
    query_id: str
    items: List[Dict[str, Any]]
    total_count: int
    returned_count: int
    aggregates: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "items": self.items,
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "aggregates": self.aggregates,
            "execution_time_ms": self.execution_time_ms,
            "cached": self.cached,
        }


class QueryEngine:
    """Advanced query engine."""
    
    def __init__(self, cache_enabled: bool = True,
                 cache_ttl_seconds: int = 300):
        self._collections: Dict[str, List[Dict[str, Any]]] = {}
        self._cache: Dict[str, Tuple[QueryResult, datetime]] = {}
        self._lock = threading.Lock()
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl_seconds
        
        # Statistics
        self._stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "by_collection": {},
        }
    
    def register_collection(self, name: str,
                           items: Optional[List[Dict[str, Any]]] = None) -> None:
        """Register a collection."""
        with self._lock:
            self._collections[name] = items or []
        
        logger.info("Collection registered: %s", name)
    
    def insert(self, collection: str, item: Dict[str, Any]) -> str:
        """Insert item into collection."""
        item_id = item.get("id", f"item_{uuid.uuid4().hex[:16]}")
        
        with self._lock:
            if collection not in self._collections:
                self._collections[collection] = []
            
            item_copy = {"id": item_id, **item}
            self._collections[collection].append(item_copy)
            
            # Invalidate cache
            self._invalidate_collection_cache(collection)
        
        return item_id
    
    def insert_many(self, collection: str,
                   items: List[Dict[str, Any]]) -> List[str]:
        """Insert multiple items."""
        ids = []
        
        with self._lock:
            if collection not in self._collections:
                self._collections[collection] = []
            
            for item in items:
                item_id = item.get("id", f"item_{uuid.uuid4().hex[:16]}")
                item_copy = {"id": item_id, **item}
                self._collections[collection].append(item_copy)
                ids.append(item_id)
            
            self._invalidate_collection_cache(collection)
        
        return ids
    
    def update(self, collection: str, filter: QueryFilter,
              updates: Dict[str, Any]) -> int:
        """Update items matching filter."""
        count = 0
        
        with self._lock:
            if collection not in self._collections:
                return 0
            
            for item in self._collections[collection]:
                if filter.evaluate(item):
                    for key, value in updates.items():
                        item[key] = value
                    count += 1
            
            self._invalidate_collection_cache(collection)
        
        return count
    
    def delete(self, collection: str, filter: QueryFilter) -> int:
        """Delete items matching filter."""
        count = 0
        
        with self._lock:
            if collection not in self._collections:
                return 0
            
            original_len = len(self._collections[collection])
            self._collections[collection] = [
                item for item in self._collections[collection]
                if not filter.evaluate(item)
            ]
            count = original_len - len(self._collections[collection])
            
            self._invalidate_collection_cache(collection)
        
        return count
    
    def query(self, query: Query) -> QueryResult:
        """Execute query."""
        import time
        start = time.time()
        
        # Check cache
        cache_key = self._get_cache_key(query)
        cached_result = self._get_cached(cache_key)
        
        if cached_result:
            self._stats["cache_hits"] += 1
            cached_result.cached = True
            return cached_result
        
        self._stats["cache_misses"] += 1
        
        with self._lock:
            if query.collection not in self._collections:
                return QueryResult(
                    query_id=query.query_id,
                    items=[],
                    total_count=0,
                    returned_count=0,
                )
            
            # Get items
            items = self._collections[query.collection]
            
            # Apply filter
            filtered = [item for item in items if query.filter.evaluate(item)]
            
            total_count = len(filtered)
            
            # Apply sorting
            if query.sort:
                filtered = self._apply_sort(filtered, query.sort)
            
            # Apply pagination
            paginated = filtered[query.offset:query.offset + query.limit]
            
            # Apply select (projection)
            if query.select:
                paginated = [self._apply_select(item, query.select) for item in paginated]
            
            # Apply aggregations
            aggregates = {}
            if query.aggregates:
                aggregates = self._apply_aggregates(filtered, query.aggregates)
            
            execution_time = (time.time() - start) * 1000
            
            result = QueryResult(
                query_id=query.query_id,
                items=paginated,
                total_count=total_count,
                returned_count=len(paginated),
                aggregates=aggregates,
                execution_time_ms=execution_time,
            )
            
            # Cache result
            self._cache_result(cache_key, result)
            
            # Update statistics
            self._stats["total_queries"] += 1
            self._stats["by_collection"][query.collection] = \
                self._stats["by_collection"].get(query.collection, 0) + 1
        
        return result
    
    def _apply_sort(self, items: List[Dict[str, Any]],
                   sort_fields: List[SortField]) -> List[Dict[str, Any]]:
        """Apply sorting to items."""
        def sort_key(item):
            keys = []
            for sf in sort_fields:
                value = item.get(sf.field)
                if value is None:
                    value = "" if sf.order == SortOrder.ASC else chr(127)
                keys.append(value)
            return tuple(keys)
        
        # Sort by each field in reverse order (last field first)
        result = items.copy()
        for sf in reversed(sort_fields):
            reverse = sf.order == SortOrder.DESC
            result.sort(key=lambda x: x.get(sf.field, ""), reverse=reverse)
        
        return result
    
    def _apply_select(self, item: Dict[str, Any],
                     fields: List[str]) -> Dict[str, Any]:
        """Apply field projection."""
        result = {}
        
        for field_path in fields:
            value = self._get_nested_field(item, field_path)
            if value is not None:
                result[field_path] = value
        
        return result
    
    def _get_nested_field(self, item: Dict[str, Any], field_path: str) -> Any:
        """Get nested field value."""
        parts = field_path.split(".")
        value = item
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value
    
    def _apply_aggregates(self, items: List[Dict[str, Any]],
                         aggregates: List[AggregateSpec]) -> Dict[str, Any]:
        """Apply aggregation functions."""
        results = {}
        
        for agg in aggregates:
            alias = agg.alias or f"{agg.function.value}_{agg.field}"
            values = [item.get(agg.field) for item in items if item.get(agg.field) is not None]
            
            if agg.function == AggregateFunction.COUNT:
                results[alias] = len(items)
            elif agg.function == AggregateFunction.SUM:
                results[alias] = sum(values) if values else 0
            elif agg.function == AggregateFunction.AVG:
                results[alias] = sum(values) / len(values) if values else 0
            elif agg.function == AggregateFunction.MIN:
                results[alias] = min(values) if values else None
            elif agg.function == AggregateFunction.MAX:
                results[alias] = max(values) if values else None
        
        return results
    
    def _get_cache_key(self, query: Query) -> str:
        """Generate cache key for query."""
        import hashlib
        key_data = str(query.to_dict())
        return f"q_{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def _get_cached(self, cache_key: str) -> Optional[QueryResult]:
        """Get cached result."""
        if not self._cache_enabled:
            return None
        
        with self._lock:
            if cache_key in self._cache:
                result, cached_at = self._cache[cache_key]
                age = (datetime.now(timezone.utc) - cached_at).total_seconds()
                
                if age < self._cache_ttl:
                    return result
                else:
                    del self._cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, result: QueryResult) -> None:
        """Cache query result."""
        if not self._cache_enabled:
            return
        
        with self._lock:
            self._cache[cache_key] = (result, datetime.now(timezone.utc))
    
    def _invalidate_collection_cache(self, collection: str) -> None:
        """Invalidate cache for collection."""
        if not self._cache_enabled:
            return
        
        with self._lock:
            # Clear all cache entries for simplicity
            self._cache.clear()
    
    def clear_cache(self) -> int:
        """Clear query cache."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def get_collection_count(self, collection: str) -> int:
        """Get item count for collection."""
        with self._lock:
            return len(self._collections.get(collection, []))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get query engine statistics."""
        with self._lock:
            cache_size = len(self._cache)
            
            return {
                **self._stats,
                "cache_size": cache_size,
                "cache_enabled": self._cache_enabled,
                "total_collections": len(self._collections),
            }
    
    def create_query(self, collection: str) -> Query:
        """Create a new query for collection."""
        return Query(
            query_id=f"qry_{uuid.uuid4().hex[:16]}",
            collection=collection,
        )
    
    def add_condition(self, query: Query, field: str,
                     op: Operator, value: Any) -> Query:
        """Add condition to query."""
        query.filter.conditions.append(QueryCondition(field, op, value))
        return query
    
    def add_sort(self, query: Query, field: str,
                order: SortOrder = SortOrder.ASC) -> Query:
        """Add sort field to query."""
        query.sort.append(SortField(field, order))
        return query
    
    def add_aggregate(self, query: Query, function: AggregateFunction,
                     field: str, alias: Optional[str] = None) -> Query:
        """Add aggregation to query."""
        query.aggregates.append(AggregateSpec(function, field, alias))
        return query


def create_query_engine(**kwargs) -> QueryEngine:
    """Factory function to create query engine."""
    return QueryEngine(**kwargs)
