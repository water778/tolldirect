"""Durability, restart, and idempotency tests."""

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


NOW = datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc)


class Durability(unittest.TestCase):
    def test_restart_between_charge_and_credit_does_not_recharge(self):
        path = tempfile.mktemp(suffix=".db")
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=15))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0)]
        crossings = [Crossing("GX-R", "V-1", "MA1", "TAG1", "Tobin", NOW, 350)]
        ez = SyntheticEzPass(accounts, crossings, {}, {"EZ-1"})
        pay = SyntheticPayments()
        first = Engine(SyntheticTnc(trips), ez, ez, pay, Store(path))
        first.ingest()
        self.assertEqual(first.get("GX-R").status, SettlementStatus.FAILED_UNRESOLVED)
        self.assertEqual(len(pay.charges), 1)
        first.store.close()

        ez.fail_accounts.clear()
        second = Engine(SyntheticTnc(trips), ez, ez, pay, Store(path))
        second.apply_official_posts()
        self.assertEqual(len(pay.charges), 1)
        second.retry("GX-R")
        self.assertEqual(len(pay.charges), 1)
        self.assertEqual(second.get("GX-R").status, SettlementStatus.RECONCILED)
        self.assertEqual(ez.by_id["EZ-1"].balance_cents, 350)
        report = second.reconcile()
        self.assertTrue(report["balanced"])

    def test_unresolved_is_not_automatically_charged_again(self):
        path = tempfile.mktemp(suffix=".db")
        trips = [Trip("T-1", "uber", "V-1", "pm_fail", NOW - timedelta(minutes=10))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0)]
        crossings = [Crossing("GX-F", "V-1", "MA1", "TAG1", "Tobin", NOW, 200)]
        pay = SyntheticPayments({"pm_fail"})
        ez = SyntheticEzPass(accounts, crossings, {})
        engine = Engine(SyntheticTnc(trips), ez, ez, pay, Store(path))
        engine.ingest()
        engine.apply_official_posts()
        engine.ingest()
        self.assertEqual(len(pay.charges), 0)
        self.assertEqual(engine.get("GX-F").status, SettlementStatus.FAILED_UNRESOLVED)

    def test_adjustment_is_idempotent_after_restart(self):
        path = tempfile.mktemp(suffix=".db")
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=10))]
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 0)]
        crossings = [Crossing("GX-A", "V-1", "MA1", "TAG1", "Tobin", NOW, 300)]
        pay = SyntheticPayments()
        ez = SyntheticEzPass(accounts, crossings, {})
        first = Engine(SyntheticTnc(trips), ez, ez, pay, Store(path))
        first.ingest()
        first.apply_commercial_adjustment("GX-A", 450)
        first.store.close()
        second = Engine(SyntheticTnc(trips), ez, ez, pay, Store(path))
        second.apply_commercial_adjustment("GX-A", 450)
        self.assertEqual(len(pay.charges), 2)
        self.assertEqual(second.get("GX-A").amount_cents, 450)
        self.assertTrue(second.reconcile()["balanced"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
