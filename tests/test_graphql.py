"""GraphQL Tests — Slice 295 (CORE ONLY)."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestGraphQL(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_get_graphql_schema(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/graphql/schema")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_execute_query(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/graphql/query", json={"query": "{ test }"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_get_graphql_types(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/graphql/types")
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
    def test_execute_mutation(self):
        with self._app().test_client() as c:
            r = c.post("/api/v1/graphql/mutate", json={"mutation": "{ test }"})
            d = json.loads(r.data)
            self.assertTrue(d.get("ok"))
if __name__ == "__main__": unittest.main()
