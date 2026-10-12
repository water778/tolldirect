"""End-to-end tests for the simulated TollDirect settlement path."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tolldirect.engine import Engine
from tolldirect.ledger import Ledger
from tolldirect.models import Trip, Crossing, EzPassAccount, SettlementStatus
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments


NOW = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)


def world(fail_tokens=None, delayed=None, extra_crossings=None):
    trips = [
        Trip("T-100", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20)),
        Trip("T-200", "lyft", "V-2", "pm_fail", NOW - timedelta(minutes=10), NOW + timedelta(minutes=30)),
    ]
    accounts = [
        EzPassAccount("EZ-1", "V-1", "4821", 2500),
        EzPassAccount("EZ-2", "V-2", "1104", 0),
    ]
    crossings = [
        Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin Bridge", NOW - timedelta(minutes=5)),
        Crossing("GX-2", "V-2", "MA2", "TAG2", "Sumner Tunnel", NOW, official_amount_cents=265),
        Crossing("GX-3", "V-9", "MA9", "TAG9", "Callahan", NOW),
    ]
    if extra_crossings:
        crossings.extend(extra_crossings)
    ez = SyntheticEzPass(accounts, crossings, delayed or {"GX-1": 350})
    pay = SyntheticPayments(fail_tokens or {"pm_fail"})
    engine = Engine(SyntheticTnc(trips), ez, ez, pay, Ledger())
    return engine, ez, pay


class EndToEnd(unittest.TestCase):
    def test_detect_match_and_wait_for_official_amount(self):
        engine, _, _ = world()
        self.assertEqual(engine.ingest(), 3)
        s = engine.get("GX-1")
        self.assertEqual(s.status, SettlementStatus.AWAITING_OFFICIAL_AMOUNT)
        self.assertEqual(s.trip_id, "T-100")
        self.assertEqual(s.ezpass_account_id, "EZ-1")
        self.assertIsNone(s.passenger_charge_id)

    def test_delayed_post_charges_passenger_and_credits_ezpass(self):
        engine, ez, pay = world()
        engine.ingest()
        applied = engine.apply_official_posts()
        self.assertEqual(applied, 1)
        s = engine.get("GX-1")
        self.assertEqual(s.status, SettlementStatus.RECONCILED)
        self.assertEqual(s.amount_cents, 350)
        self.assertIn(s.passenger_charge_id, pay.charges)
        self.assertEqual(pay.charges[s.passenger_charge_id]["token"], "pm_ok")
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 2500 + 350)
        self.assertEqual(s.ezpass_credit_id, ez.credits[0]["id"])

    def test_failed_passenger_charge_stays_unresolved(self):
        engine, ez, _ = world()
        engine.ingest()
        s = engine.get("GX-2")
        self.assertEqual(s.status, SettlementStatus.FAILED_UNRESOLVED)
        self.assertIn("passenger charge failed", s.failure_reason)
        self.assertEqual(ez.by_id["EZ-2"].balance_cents, 0)
        self.assertFalse(any(c["account_id"] == "EZ-2" for c in ez.credits))

    def test_unmatched_crossing_does_not_charge_anyone(self):
        engine, _, pay = world()
        engine.ingest()
        s = engine.get("GX-3")
        self.assertEqual(s.status, SettlementStatus.FAILED_UNRESOLVED)
        self.assertEqual(s.failure_reason, "no single active passenger trip")
        self.assertEqual(pay.charges, {})

    def test_duplicate_crossing_is_blocked(self):
        engine, ez, pay = world(extra_crossings=[Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin Bridge", NOW)])
        engine.ingest()
        self.assertEqual(engine.duplicates_blocked, 1)
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.AWAITING_OFFICIAL_AMOUNT)
        engine.apply_official_posts()
        self.assertEqual(len(pay.charges), 1)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 2850)

    def test_refund_reverses_passenger_charge(self):
        engine, _, pay = world()
        engine.ingest()
        engine.apply_official_posts()
        charge = engine.get("GX-1").passenger_charge_id
        engine.refund("GX-1")
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.REFUNDED)
        self.assertIn(charge, pay.refunds)

    def test_ledger_is_append_only_and_complete(self):
        engine, _, _ = world()
        engine.ingest()
        engine.apply_official_posts()
        kinds = [e.kind for e in engine.ledger.for_crossing("GX-1")]
        self.assertEqual(kinds[0], "crossing_detected")
        self.assertIn("matched", kinds)
        self.assertIn("passenger_charged", kinds)
        self.assertIn("credited_to_ezpass", kinds)
        self.assertIn("reconciled", kinds)
        self.assertEqual(len(engine.ledger.all()), len(set(e.entry_id for e in engine.ledger.all())))


if __name__ == "__main__":
    unittest.main(verbosity=2)
