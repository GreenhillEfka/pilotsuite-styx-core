import os
import tempfile
import unittest

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    # Allows running in minimal environments without Flask installed.
    create_app = None


class TestAppSmoke(unittest.TestCase):
    def test_create_app_and_health(self):
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))

    def test_capabilities_includes_brain_graph(self):
        if create_app is None:
            self.skipTest("Flask not installed")
        app = create_app()
        client = app.test_client()
        r = client.get("/api/v1/capabilities")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j.get("ok"))
        # Check both capabilities list and features dict
        caps = j.get("capabilities", [])
        feats = j.get("features", {})
        self.assertTrue(
            "brain_graph" in caps or "brain_graph" in feats,
            f"brain_graph not in capabilities {caps} or features {feats}"
        )


if __name__ == "__main__":
    unittest.main()
