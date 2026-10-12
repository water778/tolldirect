"""Read-only dashboard and health checks."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tolldirect.readonly import authorized, handle, health, dashboard_html, load_store


class ReadOnlyDemo(unittest.TestCase):
    def test_health_is_public_and_safe(self):
        status, kind, body = handle("GET", "/health", "")
        self.assertEqual(status, 200)
        self.assertIn("simulation", body)
        self.assertNotIn("GX-", body)
        self.assertEqual(health()["payments"], "disabled")

    def test_dashboard_requires_auth(self):
        self.assertEqual(handle("GET", "/", "")[0], 401)
        self.assertFalse(authorized("Basic bm90OnZhbGlk"))

    def test_dashboard_is_read_only_and_synthetic(self):
        status, _, body = handle("GET", "/", "Basic ZGVtbzp0b2xsZGlyZWN0LXNpbQ==")
        self.assertEqual(status, 200)
        self.assertIn("GX-2201", body)
        self.assertIn("failed_unresolved", body)
        self.assertIn("reconciled", body)
        self.assertIn("SIMULATION ONLY", body)
        self.assertIn("max-width:700px", body)
        self.assertEqual(handle("POST", "/", "Basic ZGVtbzp0b2xsZGlyZWN0LXNpbQ==")[0], 405)
        self.assertTrue(load_store().all_settlements())


if __name__ == "__main__":
    unittest.main(verbosity=2)
