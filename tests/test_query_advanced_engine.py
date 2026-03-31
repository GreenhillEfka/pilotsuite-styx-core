"""Tests for Query Engine Advanced — Slice 64."""
import pytest
from copilot_core.query_advanced.engine import (
    QueryEngine,
    Query,
    QueryFilter,
    QueryCondition,
    QueryResult,
    SortField,
    SortOrder,
    AggregateSpec,
    AggregateFunction,
    Operator,
    create_query_engine,
)
from datetime import datetime, timezone


class TestOperator:
    """Test query operators."""
    
    def test_operator_enum_values(self):
        """Test operator enum values."""
        assert Operator.EQ.value == "eq"
        assert Operator.NE.value == "ne"
        assert Operator.LT.value == "lt"
        assert Operator.GT.value == "gt"
        assert Operator.IN.value == "in"
        assert Operator.LIKE.value == "like"
        assert Operator.AND.value == "and"
        assert Operator.OR.value == "or"


class TestSortOrder:
    """Test sort order."""
    
    def test_sort_order_enum_values(self):
        """Test sort order enum values."""
        assert SortOrder.ASC.value == "asc"
        assert SortOrder.DESC.value == "desc"


class TestAggregateFunction:
    """Test aggregate functions."""
    
    def test_aggregate_enum_values(self):
        """Test aggregate function enum values."""
        assert AggregateFunction.COUNT.value == "count"
        assert AggregateFunction.SUM.value == "sum"
        assert AggregateFunction.AVG.value == "avg"
        assert AggregateFunction.MIN.value == "min"
        assert AggregateFunction.MAX.value == "max"


class TestQueryCondition:
    """Test query condition."""
    
    def test_condition_eq(self):
        """Test equality condition."""
        cond = QueryCondition("name", Operator.EQ, "John")
        
        assert cond.evaluate({"name": "John"}) is True
        assert cond.evaluate({"name": "Jane"}) is False
    
    def test_condition_ne(self):
        """Test not equal condition."""
        cond = QueryCondition("name", Operator.NE, "John")
        
        assert cond.evaluate({"name": "Jane"}) is True
        assert cond.evaluate({"name": "John"}) is False
    
    def test_condition_lt(self):
        """Test less than condition."""
        cond = QueryCondition("age", Operator.LT, 30)
        
        assert cond.evaluate({"age": 25}) is True
        assert cond.evaluate({"age": 30}) is False
        assert cond.evaluate({"age": 35}) is False
    
    def test_condition_le(self):
        """Test less than or equal condition."""
        cond = QueryCondition("age", Operator.LE, 30)
        
        assert cond.evaluate({"age": 25}) is True
        assert cond.evaluate({"age": 30}) is True
        assert cond.evaluate({"age": 35}) is False
    
    def test_condition_gt(self):
        """Test greater than condition."""
        cond = QueryCondition("age", Operator.GT, 30)
        
        assert cond.evaluate({"age": 35}) is True
        assert cond.evaluate({"age": 30}) is False
        assert cond.evaluate({"age": 25}) is False
    
    def test_condition_ge(self):
        """Test greater than or equal condition."""
        cond = QueryCondition("age", Operator.GE, 30)
        
        assert cond.evaluate({"age": 35}) is True
        assert cond.evaluate({"age": 30}) is True
        assert cond.evaluate({"age": 25}) is False
    
    def test_condition_in(self):
        """Test in condition."""
        cond = QueryCondition("status", Operator.IN, ["active", "pending"])
        
        assert cond.evaluate({"status": "active"}) is True
        assert cond.evaluate({"status": "inactive"}) is False
    
    def test_condition_nin(self):
        """Test not in condition."""
        cond = QueryCondition("status", Operator.NIN, ["inactive", "deleted"])
        
        assert cond.evaluate({"status": "active"}) is True
        assert cond.evaluate({"status": "inactive"}) is False
    
    def test_condition_like(self):
        """Test like condition with wildcards."""
        cond = QueryCondition("email", Operator.LIKE, "%@gmail.com")
        
        assert cond.evaluate({"email": "test@gmail.com"}) is True
        assert cond.evaluate({"email": "test@yahoo.com"}) is False
    
    def test_condition_contains(self):
        """Test contains condition."""
        cond = QueryCondition("name", Operator.CONTAINS, "John")
        
        assert cond.evaluate({"name": "John Doe"}) is True
        assert cond.evaluate({"name": "Jane Doe"}) is False
    
    def test_condition_exists_true(self):
        """Test exists condition (field exists)."""
        cond = QueryCondition("email", Operator.EXISTS, True)
        
        assert cond.evaluate({"email": "test@example.com"}) is True
        assert cond.evaluate({}) is False
    
    def test_condition_exists_false(self):
        """Test exists condition (field not exists)."""
        cond = QueryCondition("email", Operator.EXISTS, False)
        
        assert cond.evaluate({}) is True
        assert cond.evaluate({"email": "test@example.com"}) is False
    
    def test_condition_nested_field(self):
        """Test condition with nested field."""
        cond = QueryCondition("user.name", Operator.EQ, "John")
        
        assert cond.evaluate({"user": {"name": "John"}}) is True
        assert cond.evaluate({"user": {"name": "Jane"}}) is False
    
    def test_condition_nested_field_missing(self):
        """Test condition with missing nested field."""
        cond = QueryCondition("user.name", Operator.EQ, "John")
        
        assert cond.evaluate({"user": {}}) is False
        assert cond.evaluate({}) is False


class TestQueryFilter:
    """Test query filter."""
    
    def test_filter_empty(self):
        """Test empty filter matches all."""
        f = QueryFilter()
        
        assert f.evaluate({"any": "value"}) is True
    
    def test_filter_and(self):
        """Test filter with AND logic."""
        f = QueryFilter(
            conditions=[
                QueryCondition("age", Operator.GT, 18),
                QueryCondition("status", Operator.EQ, "active"),
            ],
            logical_op=Operator.AND,
        )
        
        assert f.evaluate({"age": 25, "status": "active"}) is True
        assert f.evaluate({"age": 25, "status": "inactive"}) is False
        assert f.evaluate({"age": 15, "status": "active"}) is False
    
    def test_filter_or(self):
        """Test filter with OR logic."""
        f = QueryFilter(
            conditions=[
                QueryCondition("age", Operator.GT, 65),
                QueryCondition("status", Operator.EQ, "senior"),
            ],
            logical_op=Operator.OR,
        )
        
        assert f.evaluate({"age": 70, "status": "active"}) is True
        assert f.evaluate({"age": 30, "status": "senior"}) is True
        assert f.evaluate({"age": 30, "status": "active"}) is False


class TestQuery:
    """Test query definition."""
    
    def test_create_query(self):
        """Test creating query."""
        q = Query(
            query_id="qry_test",
            collection="users",
            limit=50,
            offset=10,
        )
        
        assert q.query_id == "qry_test"
        assert q.collection == "users"
        assert q.limit == 50
    
    def test_query_to_dict(self):
        """Test query serialization."""
        q = Query(
            query_id="qry_test",
            collection="users",
            limit=25,
            offset=5,
        )
        q.sort.append(SortField("name", SortOrder.ASC))
        
        d = q.to_dict()
        
        assert d["query_id"] == "qry_test"
        assert d["limit"] == 25
        assert len(d["sort"]) == 1


class TestQueryResult:
    """Test query result."""
    
    def test_create_result(self):
        """Test creating query result."""
        result = QueryResult(
            query_id="qry_test",
            items=[{"id": 1}, {"id": 2}],
            total_count=100,
            returned_count=2,
        )
        
        assert result.query_id == "qry_test"
        assert len(result.items) == 2
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = QueryResult(
            query_id="qry_test",
            items=[{"id": 1}],
            total_count=50,
            returned_count=1,
            execution_time_ms=15.5,
            cached=True,
        )
        
        d = result.to_dict()
        
        assert d["cached"] is True
        assert d["execution_time_ms"] == 15.5


class TestQueryEngine:
    """Test query engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_query_engine()
        assert engine is not None
    
    def test_register_collection(self):
        """Test registering collection."""
        engine = QueryEngine()
        
        engine.register_collection("users")
        
        assert engine.get_collection_count("users") == 0
    
    def test_register_collection_with_items(self):
        """Test registering collection with items."""
        engine = QueryEngine()
        
        items = [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
        
        engine.register_collection("users", items)
        
        assert engine.get_collection_count("users") == 2
    
    def test_insert(self):
        """Test inserting item."""
        engine = QueryEngine()
        engine.register_collection("users")
        
        item_id = engine.insert("users", {"name": "John", "age": 30})
        
        assert item_id is not None
        assert engine.get_collection_count("users") == 1
    
    def test_insert_many(self):
        """Test inserting multiple items."""
        engine = QueryEngine()
        engine.register_collection("users")
        
        items = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25},
            {"name": "Bob", "age": 35},
        ]
        
        ids = engine.insert_many("users", items)
        
        assert len(ids) == 3
        assert engine.get_collection_count("users") == 3
    
    def test_query_all(self):
        """Test querying all items."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John"},
            {"id": 2, "name": "Jane"},
            {"id": 3, "name": "Bob"},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        result = engine.query(query)
        
        assert result.total_count == 3
        assert result.returned_count == 3
    
    def test_query_with_filter(self):
        """Test querying with filter."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": 25},
            {"id": 3, "name": "Bob", "age": 35},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_condition(query, "age", Operator.GT, 28)
        
        result = engine.query(query)
        
        assert result.total_count == 2  # John and Bob
    
    def test_query_with_sort(self):
        """Test querying with sorting."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": 25},
            {"id": 3, "name": "Bob", "age": 35},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_sort(query, "age", SortOrder.ASC)
        
        result = engine.query(query)
        
        assert result.items[0]["age"] == 25
        assert result.items[1]["age"] == 30
        assert result.items[2]["age"] == 35
    
    def test_query_with_sort_desc(self):
        """Test querying with descending sort."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": 25},
            {"id": 3, "name": "Bob", "age": 35},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_sort(query, "age", SortOrder.DESC)
        
        result = engine.query(query)
        
        assert result.items[0]["age"] == 35
        assert result.items[1]["age"] == 30
        assert result.items[2]["age"] == 25
    
    def test_query_with_limit(self):
        """Test querying with limit."""
        engine = QueryEngine()
        
        items = [{"id": i, "name": f"User {i}"} for i in range(10)]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        query.limit = 5
        
        result = engine.query(query)
        
        assert result.returned_count == 5
        assert result.total_count == 10
    
    def test_query_with_offset(self):
        """Test querying with offset."""
        engine = QueryEngine()
        
        items = [{"id": i, "name": f"User {i}"} for i in range(10)]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        query.limit = 5
        query.offset = 5
        
        result = engine.query(query)
        
        assert result.returned_count == 5
        assert result.items[0]["id"] == 5
    
    def test_query_with_select(self):
        """Test querying with field selection."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "age": 30, "email": "john@example.com"},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        query.select = ["name", "age"]
        
        result = engine.query(query)
        
        assert "name" in result.items[0]
        assert "age" in result.items[0]
        assert "email" not in result.items[0]
    
    def test_query_with_aggregate_count(self):
        """Test querying with count aggregation."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": 25},
            {"id": 3, "name": "Bob", "age": 35},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_aggregate(query, AggregateFunction.COUNT, "id")
        
        result = engine.query(query)
        
        assert result.aggregates["count_id"] == 3
    
    def test_query_with_aggregate_sum(self):
        """Test querying with sum aggregation."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "amount": 100},
            {"id": 2, "amount": 200},
            {"id": 3, "amount": 300},
        ]
        
        engine.register_collection("orders", items)
        
        query = engine.create_query("orders")
        engine.add_aggregate(query, AggregateFunction.SUM, "amount")
        
        result = engine.query(query)
        
        assert result.aggregates["sum_amount"] == 600
    
    def test_query_with_aggregate_avg(self):
        """Test querying with avg aggregation."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "score": 80},
            {"id": 2, "score": 90},
            {"id": 3, "score": 100},
        ]
        
        engine.register_collection("results", items)
        
        query = engine.create_query("results")
        engine.add_aggregate(query, AggregateFunction.AVG, "score")
        
        result = engine.query(query)
        
        assert result.aggregates["avg_score"] == 90.0
    
    def test_query_with_aggregate_min(self):
        """Test querying with min aggregation."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "price": 100},
            {"id": 2, "price": 50},
            {"id": 3, "price": 75},
        ]
        
        engine.register_collection("products", items)
        
        query = engine.create_query("products")
        engine.add_aggregate(query, AggregateFunction.MIN, "price")
        
        result = engine.query(query)
        
        assert result.aggregates["min_price"] == 50
    
    def test_query_with_aggregate_max(self):
        """Test querying with max aggregation."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "price": 100},
            {"id": 2, "price": 50},
            {"id": 3, "price": 75},
        ]
        
        engine.register_collection("products", items)
        
        query = engine.create_query("products")
        engine.add_aggregate(query, AggregateFunction.MAX, "price")
        
        result = engine.query(query)
        
        assert result.aggregates["max_price"] == 100
    
    def test_query_with_aggregate_alias(self):
        """Test querying with aggregate alias."""
        engine = QueryEngine()
        
        items = [{"id": 1, "value": 100}, {"id": 2, "value": 200}]
        
        engine.register_collection("data", items)
        
        query = engine.create_query("data")
        engine.add_aggregate(query, AggregateFunction.SUM, "value", alias="total")
        
        result = engine.query(query)
        
        assert result.aggregates["total"] == 300
    
    def test_update(self):
        """Test updating items."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "status": "active"},
            {"id": 2, "name": "Jane", "status": "active"},
            {"id": 3, "name": "Bob", "status": "inactive"},
        ]
        
        engine.register_collection("users", items)
        
        filter = QueryFilter(
            conditions=[QueryCondition("status", Operator.EQ, "active")],
        )
        
        count = engine.update("users", filter, {"status": "suspended"})
        
        assert count == 2
    
    def test_delete(self):
        """Test deleting items."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "status": "active"},
            {"id": 2, "name": "Jane", "status": "inactive"},
        ]
        
        engine.register_collection("users", items)
        
        filter = QueryFilter(
            conditions=[QueryCondition("status", Operator.EQ, "inactive")],
        )
        
        count = engine.delete("users", filter)
        
        assert count == 1
        assert engine.get_collection_count("users") == 1
    
    def test_query_nonexistent_collection(self):
        """Test querying nonexistent collection."""
        engine = QueryEngine()
        
        query = engine.create_query("nonexistent")
        result = engine.query(query)
        
        assert result.total_count == 0
        assert result.items == []
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = QueryEngine()
        
        engine.register_collection("users")
        engine.insert("users", {"name": "John"})
        
        query = engine.create_query("users")
        engine.query(query)
        
        stats = engine.get_statistics()
        
        assert stats["total_queries"] == 1
        assert stats["total_collections"] == 1
    
    def test_statistics_by_collection(self):
        """Test statistics by collection."""
        engine = QueryEngine()
        
        engine.register_collection("users")
        engine.register_collection("orders")
        
        engine.query(engine.create_query("users"))
        engine.query(engine.create_query("users"))
        engine.query(engine.create_query("orders"))
        
        stats = engine.get_statistics()
        
        assert stats["by_collection"]["users"] == 2
        assert stats["by_collection"]["orders"] == 1
    
    def test_cache_hit(self):
        """Test cache hit."""
        engine = QueryEngine(cache_enabled=True, cache_ttl_seconds=300)
        
        items = [{"id": 1, "name": "John"}]
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        
        # First query (cache miss)
        result1 = engine.query(query)
        
        # Second query (cache hit)
        result2 = engine.query(query)
        
        stats = engine.get_statistics()
        
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert result2.cached is True
    
    def test_clear_cache(self):
        """Test clearing cache."""
        engine = QueryEngine(cache_enabled=True)
        
        engine.register_collection("users", [{"id": 1}])
        
        # Run query to populate cache
        engine.query(engine.create_query("users"))
        engine.query(engine.create_query("users"))
        
        count = engine.clear_cache()
        
        assert count >= 1
        
        stats = engine.get_statistics()
        
        assert stats["cache_size"] == 0
    
    def test_query_execution_time(self):
        """Test that query tracks execution time."""
        engine = QueryEngine()
        
        engine.register_collection("users", [{"id": 1}])
        
        query = engine.create_query("users")
        result = engine.query(query)
        
        assert result.execution_time_ms >= 0
    
    def test_query_result_total_count(self):
        """Test that result includes total count."""
        engine = QueryEngine()
        
        items = [{"id": i} for i in range(100)]
        engine.register_collection("items", items)
        
        query = engine.create_query("items")
        query.limit = 10
        
        result = engine.query(query)
        
        assert result.total_count == 100
        assert result.returned_count == 10
    
    def test_insert_returns_id(self):
        """Test that insert returns item ID."""
        engine = QueryEngine()
        engine.register_collection("users")
        
        item_id = engine.insert("users", {"name": "John"})
        
        assert item_id is not None
        assert item_id.startswith("item_")
    
    def test_insert_with_custom_id(self):
        """Test insert with custom ID."""
        engine = QueryEngine()
        engine.register_collection("users")
        
        item_id = engine.insert("users", {"id": "custom_123", "name": "John"})
        
        assert item_id == "custom_123"
    
    def test_insert_many_returns_ids(self):
        """Test that insert_many returns IDs."""
        engine = QueryEngine()
        engine.register_collection("users")
        
        ids = engine.insert_many("users", [{"name": "John"}, {"name": "Jane"}])
        
        assert len(ids) == 2
    
    def test_update_nonexistent_collection(self):
        """Test updating nonexistent collection."""
        engine = QueryEngine()
        
        filter = QueryFilter()
        count = engine.update("nonexistent", filter, {"key": "value"})
        
        assert count == 0
    
    def test_delete_nonexistent_collection(self):
        """Test deleting from nonexistent collection."""
        engine = QueryEngine()
        
        filter = QueryFilter()
        count = engine.delete("nonexistent", filter)
        
        assert count == 0
    
    def test_get_collection_count_nonexistent(self):
        """Test getting count for nonexistent collection."""
        engine = QueryEngine()
        
        count = engine.get_collection_count("nonexistent")
        
        assert count == 0
    
    def test_query_id_unique(self):
        """Test that query IDs are unique."""
        engine = QueryEngine()
        
        ids = set()
        for i in range(50):
            query = engine.create_query("test")
            ids.add(query.query_id)
        
        assert len(ids) == 50
    
    def test_item_id_unique(self):
        """Test that item IDs are unique."""
        engine = QueryEngine()
        engine.register_collection("items")
        
        ids = set()
        for i in range(50):
            item_id = engine.insert("items", {"value": i})
            ids.add(item_id)
        
        assert len(ids) == 50
    
    def test_filter_like_wildcard_percent(self):
        """Test LIKE with % wildcard."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "email": "test@gmail.com"},
            {"id": 2, "email": "test@yahoo.com"},
            {"id": 3, "email": "admin@gmail.com"},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_condition(query, "email", Operator.LIKE, "%@gmail.com")
        
        result = engine.query(query)
        
        assert result.total_count == 2
    
    def test_filter_like_wildcard_underscore(self):
        """Test LIKE with _ wildcard (single char)."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "code": "A1"},
            {"id": 2, "code": "A2"},
            {"id": 3, "code": "B1"},
        ]
        
        engine.register_collection("items", items)
        
        query = engine.create_query("items")
        engine.add_condition(query, "code", Operator.LIKE, "A_")
        
        result = engine.query(query)
        
        assert result.total_count == 2
    
    def test_sort_multiple_fields(self):
        """Test sorting by multiple fields."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "dept": "A", "salary": 5000},
            {"id": 2, "dept": "A", "salary": 6000},
            {"id": 3, "dept": "B", "salary": 5000},
            {"id": 4, "dept": "B", "salary": 6000},
        ]
        
        engine.register_collection("employees", items)
        
        query = engine.create_query("employees")
        engine.add_sort(query, "dept", SortOrder.ASC)
        engine.add_sort(query, "salary", SortOrder.DESC)
        
        result = engine.query(query)
        
        # Should be sorted by dept ASC, then salary DESC
        assert result.items[0]["dept"] == "A"
        assert result.items[0]["salary"] == 6000
    
    def test_aggregate_with_filter(self):
        """Test aggregation with filter."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "status": "active", "amount": 100},
            {"id": 2, "status": "active", "amount": 200},
            {"id": 3, "status": "inactive", "amount": 300},
        ]
        
        engine.register_collection("orders", items)
        
        query = engine.create_query("orders")
        engine.add_condition(query, "status", Operator.EQ, "active")
        engine.add_aggregate(query, AggregateFunction.SUM, "amount")
        
        result = engine.query(query)
        
        assert result.aggregates["sum_amount"] == 300
        assert result.total_count == 2
    
    def test_statistics_cache_enabled(self):
        """Test that statistics track cache enabled status."""
        engine = QueryEngine(cache_enabled=True)
        
        stats = engine.get_statistics()
        
        assert stats["cache_enabled"] is True
    
    def test_statistics_cache_disabled(self):
        """Test statistics with cache disabled."""
        engine = QueryEngine(cache_enabled=False)
        
        stats = engine.get_statistics()
        
        assert stats["cache_enabled"] is False
    
    def test_nested_field_projection(self):
        """Test selecting nested fields."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "user": {"name": "John", "email": "john@example.com"}},
        ]
        
        engine.register_collection("data", items)
        
        query = engine.create_query("data")
        query.select = ["user.name"]
        
        result = engine.query(query)
        
        assert "user.name" in result.items[0]
        assert result.items[0]["user.name"] == "John"
    
    def test_query_created_at_set(self):
        """Test that query created_at is set."""
        engine = QueryEngine()
        
        query = engine.create_query("test")
        
        assert query.created_at is not None
    
    def test_result_cached_flag(self):
        """Test that result cached flag is set correctly."""
        engine = QueryEngine(cache_enabled=True)
        engine.register_collection("test", [{"id": 1}])
        
        query = engine.create_query("test")
        
        result1 = engine.query(query)
        result2 = engine.query(query)
        
        assert result1.cached is False
        assert result2.cached is True
    
    def test_insert_invalidates_cache(self):
        """Test that insert invalidates cache."""
        engine = QueryEngine(cache_enabled=True)
        engine.register_collection("test", [{"id": 1}])
        
        query = engine.create_query("test")
        
        # Populate cache
        engine.query(query)
        engine.query(query)
        
        # Insert should invalidate
        engine.insert("test", {"id": 2})
        
        # Next query should be cache miss
        result = engine.query(query)
        
        stats = engine.get_statistics()
        
        # Should have 3 misses now (initial + after invalidate)
        assert stats["cache_misses"] >= 2
    
    def test_delete_invalidates_cache(self):
        """Test that delete invalidates cache."""
        engine = QueryEngine(cache_enabled=True)
        engine.register_collection("test", [{"id": 1}, {"id": 2}])
        
        query = engine.create_query("test")
        engine.query(query)
        engine.query(query)
        
        filter = QueryFilter(
            conditions=[QueryCondition("id", Operator.EQ, 2)],
        )
        engine.delete("test", filter)
        
        # Cache should be invalidated
        result = engine.query(query)
        
        assert result.cached is False
    
    def test_update_invalidates_cache(self):
        """Test that update invalidates cache."""
        engine = QueryEngine(cache_enabled=True)
        engine.register_collection("test", [{"id": 1, "value": 10}])
        
        query = engine.create_query("test")
        engine.query(query)
        
        filter = QueryFilter(
            conditions=[QueryCondition("id", Operator.EQ, 1)],
        )
        engine.update("test", filter, {"value": 20})
        
        # Cache should be invalidated
        result = engine.query(query)
        
        assert result.cached is False
    
    def test_query_empty_collection(self):
        """Test querying empty collection."""
        engine = QueryEngine()
        engine.register_collection("empty")
        
        query = engine.create_query("empty")
        result = engine.query(query)
        
        assert result.total_count == 0
        assert result.items == []
    
    def test_aggregate_empty_result(self):
        """Test aggregation on empty result."""
        engine = QueryEngine()
        engine.register_collection("empty", [])
        
        query = engine.create_query("empty")
        engine.add_aggregate(query, AggregateFunction.SUM, "value")
        
        result = engine.query(query)
        
        assert result.aggregates["sum_value"] == 0
    
    def test_aggregate_avg_empty_result(self):
        """Test avg aggregation on empty result."""
        engine = QueryEngine()
        engine.register_collection("empty", [])
        
        query = engine.create_query("empty")
        engine.add_aggregate(query, AggregateFunction.AVG, "value")
        
        result = engine.query(query)
        
        assert result.aggregates["avg_value"] == 0
    
    def test_aggregate_min_empty_result(self):
        """Test min aggregation on empty result."""
        engine = QueryEngine()
        engine.register_collection("empty", [])
        
        query = engine.create_query("empty")
        engine.add_aggregate(query, AggregateFunction.MIN, "value")
        
        result = engine.query(query)
        
        assert result.aggregates["min_value"] is None
    
    def test_aggregate_max_empty_result(self):
        """Test max aggregation on empty result."""
        engine = QueryEngine()
        engine.register_collection("empty", [])
        
        query = engine.create_query("empty")
        engine.add_aggregate(query, AggregateFunction.MAX, "value")
        
        result = engine.query(query)
        
        assert result.aggregates["max_value"] is None
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = QueryEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_queries"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        assert stats["total_collections"] == 0
    
    def test_multiple_collections_independent(self):
        """Test that multiple collections are independent."""
        engine = QueryEngine()
        
        engine.register_collection("users", [{"id": 1, "name": "John"}])
        engine.register_collection("orders", [{"id": 1, "product": "Widget"}])
        
        users_query = engine.create_query("users")
        orders_query = engine.create_query("orders")
        
        users_result = engine.query(users_query)
        orders_result = engine.query(orders_query)
        
        assert users_result.total_count == 1
        assert "name" in users_result.items[0]
        
        assert orders_result.total_count == 1
        assert "product" in orders_result.items[0]
    
    def test_condition_case_sensitive(self):
        """Test that conditions are case sensitive."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John"},
            {"id": 2, "name": "john"},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_condition(query, "name", Operator.EQ, "John")
        
        result = engine.query(query)
        
        assert result.total_count == 1
    
    def test_filter_condition_order(self):
        """Test that filter conditions are evaluated in order."""
        # AND/OR logic doesn't depend on order, but we test evaluation
        f = QueryFilter(
            conditions=[
                QueryCondition("a", Operator.EQ, 1),
                QueryCondition("b", Operator.EQ, 2),
                QueryCondition("c", Operator.EQ, 3),
            ],
            logical_op=Operator.AND,
        )
        
        assert f.evaluate({"a": 1, "b": 2, "c": 3}) is True
        assert f.evaluate({"a": 1, "b": 2, "c": 4}) is False
    
    def test_query_to_dict_includes_all_fields(self):
        """Test that query to_dict includes all fields."""
        engine = QueryEngine()
        
        query = engine.create_query("test")
        engine.add_condition(query, "name", Operator.EQ, "John")
        engine.add_sort(query, "age", SortOrder.DESC)
        engine.add_aggregate(query, AggregateFunction.COUNT, "id")
        query.limit = 50
        query.offset = 10
        query.select = ["name", "age"]
        
        d = query.to_dict()
        
        assert len(d["filter"]["conditions"]) == 1
        assert len(d["sort"]) == 1
        assert len(d["aggregates"]) == 1
        assert d["limit"] == 50
        assert d["offset"] == 10
        assert d["select"] == ["name", "age"]
    
    def test_result_to_dict_includes_all_fields(self):
        """Test that result to_dict includes all fields."""
        result = QueryResult(
            query_id="qry_test",
            items=[{"id": 1}],
            total_count=100,
            returned_count=1,
            aggregates={"count": 100},
            execution_time_ms=5.5,
            cached=False,
        )
        
        d = result.to_dict()
        
        assert d["query_id"] == "qry_test"
        assert d["total_count"] == 100
        assert d["aggregates"]["count"] == 100
        assert d["execution_time_ms"] == 5.5
        assert d["cached"] is False
    
    def test_insert_many_empty_list(self):
        """Test insert_many with empty list."""
        engine = QueryEngine()
        engine.register_collection("test")
        
        ids = engine.insert_many("test", [])
        
        assert len(ids) == 0
        assert engine.get_collection_count("test") == 0
    
    def test_query_with_null_values(self):
        """Test querying with null values."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "email": "john@example.com"},
            {"id": 2, "name": "Jane", "email": None},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_condition(query, "email", Operator.EXISTS, False)
        
        result = engine.query(query)
        
        assert result.total_count == 1
        assert result.items[0]["name"] == "Jane"
    
    def test_sort_with_null_values(self):
        """Test sorting with null values."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": None},
            {"id": 3, "name": "Bob", "age": 25},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        engine.add_sort(query, "age", SortOrder.ASC)
        
        result = engine.query(query)
        
        # Null values should sort first in ASC
        assert result.items[0]["name"] == "Jane"
    
    def test_clear_cache_empty(self):
        """Test clearing empty cache."""
        engine = QueryEngine(cache_enabled=True)
        
        count = engine.clear_cache()
        
        assert count == 0
    
    def test_create_query_sets_collection(self):
        """Test that create_query sets collection."""
        engine = QueryEngine()
        
        query = engine.create_query("my_collection")
        
        assert query.collection == "my_collection"
    
    def test_add_condition_returns_query(self):
        """Test that add_condition returns query for chaining."""
        engine = QueryEngine()
        
        query = engine.create_query("test")
        result = engine.add_condition(query, "name", Operator.EQ, "John")
        
        assert result is query
        assert len(query.filter.conditions) == 1
    
    def test_add_sort_returns_query(self):
        """Test that add_sort returns query for chaining."""
        engine = QueryEngine()
        
        query = engine.create_query("test")
        result = engine.add_sort(query, "name", SortOrder.ASC)
        
        assert result is query
        assert len(query.sort) == 1
    
    def test_add_aggregate_returns_query(self):
        """Test that add_aggregate returns query for chaining."""
        engine = QueryEngine()
        
        query = engine.create_query("test")
        result = engine.add_aggregate(query, AggregateFunction.COUNT, "id")
        
        assert result is query
        assert len(query.aggregates) == 1
    
    def test_chained_query_builder(self):
        """Test chained query building."""
        engine = QueryEngine()
        engine.register_collection("users", [
            {"id": 1, "name": "John", "age": 30},
            {"id": 2, "name": "Jane", "age": 25},
            {"id": 3, "name": "Bob", "age": 35},
        ])
        
        query = engine.create_query("users")
        engine.add_condition(query, "age", Operator.GT, 25)
        engine.add_sort(query, "age", SortOrder.DESC)
        engine.add_aggregate(query, AggregateFunction.COUNT, "id")
        query.limit = 10
        
        result = engine.query(query)
        
        assert result.total_count == 2
        assert result.aggregates["count_id"] == 2
    
    def test_query_with_special_characters_in_like(self):
        """Test LIKE pattern with special regex characters."""
        engine = QueryEngine()
        
        items = [
            {"id": 1, "name": "John (Senior)"},
            {"id": 2, "name": "Jane (Junior)"},
        ]
        
        engine.register_collection("users", items)
        
        query = engine.create_query("users")
        # Parentheses are special in regex
        engine.add_condition(query, "name", Operator.LIKE, "%(Senior)%")
        
        result = engine.query(query)
        
        assert result.total_count == 1
