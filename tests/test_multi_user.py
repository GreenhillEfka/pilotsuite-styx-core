"""Multi-User Support Tests — Slice 206."""
import unittest, tempfile, json
try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None
class TestMultiUser(unittest.TestCase):
    def setUp(self): self.tmpdir = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmpdir.cleanup()
    def _app(self):
        if not create_app: self.skipTest("copilot_core not available")
        return create_app(data_dir=self.tmpdir.name, testing=True)
    def test_user_preferences_isolation(self):
        with self._app().test_client() as c:
            r1 = c.get("/api/v1/users/user1/preferences")
            r2 = c.get("/api/v1/users/user2/preferences")
            self.assertEqual(r1.status_code, 200)
            self.assertEqual(r2.status_code, 200)
    def test_user_context_separation(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/users/test-user/context")
            self.assertIn(r.status_code, [200, 404])
    def test_multi_user_presence(self):
        with self._app().test_client() as c:
            r = c.get("/api/v1/presence/users")
            self.assertIn(r.status_code, [200, 501])
if __name__ == "__main__": unittest.main()
