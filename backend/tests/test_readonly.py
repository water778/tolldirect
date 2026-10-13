"""Read-only dashboard and health checks."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tolldirect.readonly import authorized, handle, health, dashboard_html, load_store


class ReadOnlyDemo(unittest.TestCase):
    def test_health_is_public_and_safe(self):
        status, kind, body = handle("GET", "/health", "")
        self.assertEqual(status, 200)
        self.assertIn("simulation", body)
        self.assertNotIn("GX-", body)
        self.assertEqual(health()["payments"], "disabled")

    def test_dashboard_disabled_without_password(self):
        with patch.dict(os.environ, {}, clear=True):
            # Ensure the module sees no password
            import importlib
            import tolldirect.readonly as ro
            importlib.reload(ro)
            self.assertEqual(ro.handle("GET", "/", "")[0], 503)
            self.assertFalse(ro.authorized("Basic bm90OnZhbGlk"))

    def test_dashboard_is_read_only_and_synthetic(self):
        test_password = "local-test-only"
        with patch.dict(os.environ, {"TOLLDIRECT_DEMO_PASSWORD": test_password}):
            import importlib
            import tolldirect.readonly as ro
            importlib.reload(ro)
            import base64
            auth = "Basic " + base64.b64encode(f"demo:{test_password}".encode()).decode()
            status, _, body = ro.handle("GET", "/", auth)
            self.assertEqual(status, 200)
            self.assertIn("GX-2201", body)
            self.assertIn("failed_unresolved", body)
            self.assertIn("reconciled", body)
            self.assertIn("SIMULATION ONLY", body)
            self.assertIn("max-width:700px", body)
            self.assertEqual(ro.handle("POST", "/", auth)[0], 405)
            self.assertTrue(ro.load_store().all_settlements())


if __name__ == "__main__":
    unittest.main(verbosity=2)
