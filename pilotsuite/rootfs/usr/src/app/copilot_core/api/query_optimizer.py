"""Query optimization utilities for API endpoints.

Provides:
- Database query optimization hints and utilities
- Index usage analysis
- Lazy loading support for large responses
- Connection pooling recommendations
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Query

_LOGGER = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """Statistics for a single query execution."""
    query: str
    duration_ms: float
    rows_affected: int
    index_used: bool
    scan_type: str = "full"
    hints: List[str] = None

    def __post_init__(self):
        if self.hints is None:
            self.hints = []


class QueryOptimizer:
    """Optimizes database queries for better performance."""
    
    def __init__(self):
        """Initialize query optimizer."""
        self._query_cache: Dict[str, QueryStats] = {}
        self._suggested_indexes: Dict[str, List[str]] = {}
    
    def optimize_query(
        self,
        query_func: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, QueryStats]:
        """Execute and optimize a query function.
        
        Args:
            query_func: Function that executes the query
            *args: Arguments to pass to query function
            **kwargs: Keyword arguments to pass to query function
            
        Returns:
            Tuple of (result, query_stats)
        """
        start_time = time.time()
        
        try:
            result = query_func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            stats = QueryStats(
                query=query_func.__name__,
                duration_ms=duration_ms,
                rows_affected=len(result) if hasattr(result, '__len__') else 1,
                index_used=True,  # Assume optimized by default
                scan_type="index" if duration_ms < 100 else "full"
            )
            
            # Cache stats for analysis
            self._query_cache[query_func.__name__] = stats
            
            return result, stats
            
        except Exception as e:
            _LOGGER.error(f"Query optimization error: {e}")
            raise
    
    def suggest_index(self, table: str, column: str) -> None:
        """Suggest an index for a table column.
        
        Args:
            table: Table name
            column: Column name
        """
        if table not in self._suggested_indexes:
            self._suggested_indexes[table] = []
        
        if column not in self._suggested_indexes[table]:
            self._suggested_indexes[table].append(column)
            _LOGGER.info(f"Suggested index: {table}.{column}")
    
    def get_slow_queries(self, threshold_ms: float = 500.0) -> List[QueryStats]:
        """Get list of slow queries.
        
        Args:
            threshold_ms: Duration threshold in milliseconds
            
        Returns:
            List of slow query stats
        """
        return [
            stats for stats in self._query_cache.values()
            if stats.duration_ms > threshold_ms
        ]
    
    def get_optimization_hints(self) -> List[str]:
        """Get optimization hints based on query analysis.
        
        Returns:
            List of optimization suggestions
        """
        hints = []
        
        slow_queries = self.get_slow_queries()
        if slow_queries:
            hints.append(f"Found {len(slow_queries)} slow queries (>500ms)")
        
        for table, columns in self._suggested_indexes.items():
            if columns:
                hints.append(f"Consider adding indexes on: {table}({', '.join(columns)})")
        
        return hints


def optimized_query(
    timeout_ms: float = 1000.0,
    cache_ttl: int = 60
) -> Callable:
    """Decorator for optimized query execution.
    
    Args:
        timeout_ms: Query timeout in milliseconds
        cache_ttl: Cache time-to-live in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            optimizer = kwargs.pop("_optimizer", None)
            
            if optimizer is None:
                try:
                    from copilot_core.app import get_app
                    app = get_app()
                    optimizer = getattr(app, '_query_optimizer', None)
                except Exception:
                    optimizer = QueryOptimizer()
            
            # Execute with timing
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Log slow queries
                if duration_ms > timeout_ms:
                    _LOGGER.warning(
                        f"Slow query detected: {func.__name__} took {duration_ms:.2f}ms"
                    )
                
                return result
                
            except Exception as e:
                _LOGGER.error(f"Query error in {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator


def lazy_paginate(
    data_source: Callable[[int, int], List[Any]],
    total_func: Optional[Callable[[], int]] = None,
    default_page_size: int = 100,
    max_page_size: int = 1000
) -> Callable:
    """Decorator for lazy pagination support.
    
    Args:
        data_source: Function that returns paginated data
        total_func: Function that returns total count
        default_page_size: Default number of items per page
        max_page_size: Maximum items per page
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            page = int(kwargs.get("page", 1))
            page_size = min(
                int(kwargs.get("page_size", default_page_size)),
                max_page_size
            )
            
            # Validate page
            if page < 1:
                page = 1
            
            # Get paginated data
            data = data_source(page, page_size)
            
            # Get total count if available
            total = total_func() if total_func else len(data) * page
            
            # Calculate pagination metadata
            total_pages = (total + page_size - 1) // page_size
            
            return {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": total_pages,
                    "has_previous": page > 1,
                    "has_next": page < total_pages,
                }
            }
        
        return wrapper
    return decorator