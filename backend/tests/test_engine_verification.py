"""Independent verification of the TollDirect settlement engine."""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tolldirect.engine import Engine
from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount, SettlementStatus
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments


NOW = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)


def build(trips, accounts, crossings, delayed=None, fail_tokens=None, fail_accounts=None):
    ez = SyntheticEzPass(accounts, crossings, delayed or {}, fail_accounts or set())
    pay = SyntheticPayments(fail_tokens or set())
    engine = Engine(SyntheticTnc(trips), ez, ez, pay, Store(tempfile.mktemp(suffix=".db")))
    return engine, ez, pay


class EngineVerification(unittest.TestCase):
    def test_overlapping_trips_are_not_charged(self):
        trips = [
            Trip("T-A", "uber", "V-1", "pm_a", NOW - timedelta(minutes=30)),
            Trip("T-B", "lyft", "V-1", "pm_b", NOW - timedelta(minutes=10)),
        ]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 1000)]
        crossings = [Crossing("GX-O", "V-1", "MA1", "TAG1", "Tobin", NOW)]
        engine, ez, pay = build(trips, accounts, crossings)
        engine.ingest()
        s = engine.get("GX-O")
        self.assertEqual(s.status, SettlementStatus.FAILED_UNRESOLVED)
        self.assertEqual(s.failure_reason, "no single active passenger trip")
        self.assertEqual(pay.charges, {})
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 1000)

    def test_duplicate_event_does_not_change_or_recharge_original(self):
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 2500)]
        crossings = [
            Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW - timedelta(minutes=5)),
            Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW),
        ]
        engine, ez, pay = build(trips, accounts, crossings, {"GX-1": 350})
        engine.ingest()
        self.assertEqual(engine.duplicates_blocked, 1)
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.AWAITING_OFFICIAL_AMOUNT)
        engine.apply_official_posts()
        self.assertEqual(len(pay.charges), 1)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 2850)
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.RECONCILED)

    def test_delayed_post_then_credit_to_correct_account(self):
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 100), EzPassAccount("EZ-9", "V-9", "9999", 5000)]
        crossings = [Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW - timedelta(minutes=2))]
        engine, ez, pay = build(trips, accounts, crossings, {"GX-1": 350})
        engine.ingest()
        self.assertIsNone(engine.get("GX-1").passenger_charge_id)
        engine.apply_official_posts()
        s = engine.get("GX-1")
        self.assertEqual(s.ezpass_account_id, "EZ-1")
        self.assertEqual(pay.charges[s.passenger_charge_id]["token"], "pm_ok")
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 450)
        self.assertEqual(ez.by_id["EZ-9"].balance_cents, 5000)

    def test_commercial_adjustment_is_a_delta_not_a_second_full_charge(self):
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0)]
        crossings = [Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 300)]
        engine, ez, pay = build(trips, accounts, crossings)
        engine.ingest()
        engine.apply_commercial_adjustment("GX-1", 450)
        self.assertEqual(engine.get("GX-1").amount_cents, 450)
        self.assertEqual(sum(c["amount_cents"] for c in pay.charges.values()), 450)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 450)
        self.assertEqual(len(pay.charges), 2)
        self.assertEqual(len([c for c in pay.charges.values() if c["reference"] == "GX-1"]), 1)

    def test_passenger_charge_failure_stays_unresolved_and_retryable(self):
        trips = [Trip("T-1", "uber", "V-1", "pm_fail", NOW - timedelta(minutes=10))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0)]
        crossings = [Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 265)]
        engine, ez, pay = build(trips, accounts, crossings, fail_tokens={"pm_fail"})
        engine.ingest()
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.FAILED_UNRESOLVED)
        self.assertEqual(ez.credits, [])
        pay.fail_tokens.clear()
        engine.retry("GX-1")
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.RECONCILED)
        self.assertEqual(len(pay.charges), 1)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 265)

    def test_credit_failure_after_charge_is_not_reconciled_and_retry_does_not_recharge(self):
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=10))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0)]
        crossings = [Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 265)]
        engine, ez, pay = build(trips, accounts, crossings, fail_accounts={"EZ-1"})
        engine.ingest()
        s = engine.get("GX-1")
        self.assertEqual(s.status, SettlementStatus.FAILED_UNRESOLVED)
        self.assertIsNotNone(s.passenger_charge_id)
        self.assertIsNone(s.ezpass_credit_id)
        self.assertNotEqual(s.status, SettlementStatus.RECONCILED)
        ez.fail_accounts.clear()
        engine.retry("GX-1")
        self.assertEqual(len(pay.charges), 1)
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.RECONCILED)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 265)

    def test_refund_reverses_passenger_and_ezpass(self):
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=10))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 1000)]
        crossings = [Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 265)]
        engine, ez, pay = build(trips, accounts, crossings)
        engine.ingest()
        engine.refund("GX-1")
        self.assertEqual(engine.get("GX-1").status, SettlementStatus.REFUNDED)
        self.assertEqual(len(pay.refunds), 1)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 1000)

    def test_unique_ids_and_ledger_balances(self):
        trips = [
            Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20)),
            Trip("T-2", "lyft", "V-2", "pm_bad", NOW - timedelta(minutes=10)),
        ]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0), EzPassAccount("EZ-2", "V-2", "1104", 0)]
        crossings = [
            Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW - timedelta(minutes=3)),
            Crossing("GX-2", "V-2", "MA2", "TAG2", "Sumner", NOW, 200),
            Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW),
        ]
        engine, _, _ = build(trips, accounts, crossings, {"GX-1": 350}, {"pm_bad"})
        engine.ingest()
        engine.apply_official_posts()
        ids = [e.entry_id for e in engine.store.ledger()]
        self.assertEqual(len(ids), len(set(ids)))
        report = engine.reconcile()
        self.assertTrue(report["balanced"])
        self.assertIn("GX-2", report["unresolved"])
        self.assertEqual(report["duplicates_blocked"], 1)
        self.assertEqual(report["charged_cents"], 350)
        self.assertEqual(report["credited_cents"], 350)


if __name__ == "__main__":
    unittest.main(verbosity=2)
