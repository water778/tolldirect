"""Assertions for the complete proof-of-concept workflow."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poc_demo import run
from tolldirect.models import SettlementStatus


class ProofOfConcept(unittest.TestCase):
    def test_complete_workflow(self):
        path = tempfile.mktemp(suffix=".db")
        result = run(path)
        self.assertEqual(result["matched_status"], SettlementStatus.RECONCILED)
        self.assertEqual(result["matched_trip"], "T-UBER-100")
        self.assertEqual(result["matched_account"], "EZ-MA-441")
        self.assertEqual(result["amount_cents"], 350)
        self.assertEqual(result["duplicates_blocked"], 1)
        self.assertEqual(result["charges"], 1)
        self.assertTrue(result["balanced"])
        self.assertEqual(result["failed_status"], SettlementStatus.FAILED_UNRESOLVED)
        self.assertFalse(result["early_exposed"])
        self.assertTrue(result["late_exposed"])
        kinds = [entry.kind for entry in result["ledger"] if entry.crossing_id == "GX-TOBIN-2201"]
        self.assertIn("crossing_detected", kinds)
        self.assertIn("matched", kinds)
        self.assertIn("passenger_charged", kinds)
        self.assertIn("credited_to_ezpass", kinds)
        self.assertIn("reconciled", kinds)
        self.assertIn("duplicate_blocked", kinds)


if __name__ == "__main__":
    unittest.main(verbosity=2)
