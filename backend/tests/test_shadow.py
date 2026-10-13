"""Shadow-test checks. No external calls."""

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shadow import shadow, Handler
from http.server import ThreadingHTTPServer


class ShadowLogic(unittest.TestCase):
    def test_matching_amounts_reconcile_to_ezpass(self):
        result = shadow({
            "tnc": "uber",
            "trip_ref": "1001",
            "vehicle_ref": "V-441",
            "ezpass_last4": "4821",
            "gantry": "Tobin Bridge",
            "uber_toll_cents": 350,
            "ezpass_toll_cents": 350,
            "ezpass_balance_cents": 0,
        })
        self.assertTrue(result["simulation_only"])
        self.assertFalse(result["realtime_ezpass_credit_verified"])
        self.assertFalse(result["driver_funding_used"])
        self.assertEqual(result["destination_kind"], "ezpass_account")
        self.assertEqual(result["proposed_passenger_charge"], "$3.50")
        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(result["ezpass_last4"], "4821")
        self.assertTrue(result["balanced"])
        self.assertTrue(result["zero_balance_exposed"])

    def test_higher_trip_toll_does_not_invent_a_charge(self):
        result = shadow({
            "trip_ref": "1002",
            "vehicle_ref": "V-1",
            "ezpass_last4": "1104",
            "uber_toll_cents": 500,
            "ezpass_toll_cents": 350,
            "ezpass_balance_cents": 2000,
        })
        self.assertEqual(result["proposed_passenger_charge"], "$3.50")
        self.assertEqual(result["difference"], "$1.50")
        self.assertFalse(result["zero_balance_exposed"])

    def test_full_card_number_is_rejected(self):
        with self.assertRaises(ValueError):
            shadow({"trip_ref": "4111111111111111", "ezpass_toll_cents": 350, "uber_toll_cents": 350})

    def test_password_field_is_rejected(self):
        with self.assertRaises(ValueError):
            shadow({"password": "secret", "ezpass_toll_cents": 350, "uber_toll_cents": 350})


class ShadowServer(unittest.TestCase):
    def test_mobile_page_and_api(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
            self.assertIn("viewport", page)
            self.assertIn("Simulation only", page)
            self.assertNotIn("overflow-x: auto", page)
            body = json.dumps({
                "trip_ref": "88",
                "vehicle_ref": "V-9",
                "ezpass_last4": "4821",
                "gantry": "Tobin Bridge",
                "uber_toll_cents": 350,
                "ezpass_toll_cents": 350,
            }).encode()
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/shadow",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            result = json.loads(urllib.request.urlopen(request).read().decode())
            self.assertEqual(result["status"], "reconciled")
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)
