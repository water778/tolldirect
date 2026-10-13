"""End-to-end tests for the provider-independent adapter boundary."""

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount, SettlementStatus
from tolldirect.adapters.providers import (
    SyntheticTripProvider,
    SyntheticCrossingProvider,
    SyntheticPaymentProvider,
    SyntheticEzPassProvider,
)
from tolldirect.adapters.integration import IntegrationRunner


NOW = datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc)


def runner(trips=None, accounts=None, fail_tokens=None, fail_accounts=None):
    if trips is None:
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20))]
    if accounts is None:
        accounts = [EzPassAccount("EZ-1", "V-1", "4821", 1500)]
    store = Store(tempfile.mktemp(suffix=".db"))
    return IntegrationRunner(
        SyntheticTripProvider(trips),
        SyntheticCrossingProvider([]),
        SyntheticPaymentProvider(fail_tokens),
        SyntheticEzPassProvider(accounts, fail_accounts),
        store,
    )


class AdapterIntegration(unittest.TestCase):
    def test_delayed_official_amount_then_confirmed_report(self):
        box = runner()
        crossing = Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW - timedelta(minutes=3))
        box.apply_events([
            {"event_id": "E1", "kind": "crossing", "crossing": crossing},
        ])
        pending = box.report("GX-1")
        self.assertEqual(pending.confirmation_status, SettlementStatus.AWAITING_OFFICIAL_AMOUNT.value)
        self.assertIsNone(pending.passenger_charge_id)
        box.apply_events([
            {"event_id": "E2", "kind": "official_amount", "crossing_id": "GX-1", "amount_cents": 350},
        ])
        report = box.report("GX-1")
        box.assert_no_driver_funding(report)
        self.assertEqual(report.confirmation_status, "confirmed_ezpass_credit")
        self.assertEqual(report.destination_kind, "ezpass_account")
        self.assertEqual(report.ezpass_account_id, "EZ-1")
        self.assertEqual(report.ezpass_last4, "4821")
        self.assertEqual(report.amount_cents, 350)
        self.assertIn("passenger_charged", report.audit_trail)
        self.assertIn("credited_to_ezpass", report.audit_trail)
        self.assertTrue(report.simulation_only)
        self.assertFalse(report.driver_funding_used)

    def test_duplicate_and_out_of_order_events_are_exactly_once(self):
        box = runner()
        crossing = Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW)
        # Official amount arrives before the crossing, then the crossing is repeated.
        box.apply_events([
            {"event_id": "AMT", "kind": "official_amount", "crossing_id": "GX-1", "amount_cents": 265},
            {"event_id": "CR1", "kind": "crossing", "crossing": Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 265)},
            {"event_id": "CR1", "kind": "crossing", "crossing": crossing},
        ])
        self.assertEqual(len(box.payments.charges), 1)
        self.assertEqual(box.ezpass.by_id["EZ-1"].balance_cents, 1500 + 265)
        self.assertEqual(box.report("GX-1").confirmation_status, "confirmed_ezpass_credit")

    def test_partial_failure_retry_does_not_recharge(self):
        box = runner(fail_accounts={"EZ-1"})
        box.apply_events([
            {"event_id": "CR", "kind": "crossing", "crossing": Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 200)},
        ])
        first = box.report("GX-1")
        self.assertEqual(first.confirmation_status, "charged_pending_credit")
        self.assertEqual(len(box.payments.charges), 1)
        box.ezpass.fail_accounts.clear()
        box.apply_events([{"event_id": "RT", "kind": "retry", "crossing_id": "GX-1"}])
        self.assertEqual(len(box.payments.charges), 1)
        self.assertEqual(box.report("GX-1").confirmation_status, "confirmed_ezpass_credit")
        self.assertEqual(box.ezpass.by_id["EZ-1"].balance_cents, 1500 + 200)

    def test_refund_and_adjustment_stay_on_same_crossing(self):
        box = runner(accounts=[EzPassAccount("EZ-1", "V-1", "4821", 0)])
        box.apply_events([
            {"event_id": "CR", "kind": "crossing", "crossing": Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 300)},
            {"event_id": "ADJ", "kind": "adjustment", "crossing_id": "GX-1", "new_total_cents": 450},
        ])
        self.assertEqual(sum(row["amount_cents"] for row in box.payments.charges.values()), 450)
        self.assertEqual(len([row for row in box.payments.charges.values() if row["reference"] == "GX-1"]), 1)
        box.apply_events([{"event_id": "RF", "kind": "refund", "crossing_id": "GX-1"}])
        report = box.report("GX-1")
        self.assertEqual(report.confirmation_status, "refunded")
        box.assert_no_driver_funding(report)

    def test_insufficient_funds_does_not_create_driver_recharge(self):
        box = runner(accounts=[EzPassAccount("EZ-1", "V-1", "4821", 0)])
        box.apply_events([
            {"event_id": "CR", "kind": "crossing", "crossing": Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 350)},
        ])
        report = box.report("GX-1")
        self.assertEqual(report.funds_risk, "insufficient_at_travel")
        self.assertEqual(report.confirmation_status, "confirmed_ezpass_credit")
        self.assertEqual(report.ezpass_account_id, "EZ-1")
        self.assertFalse(report.driver_funding_used)
        box.assert_no_driver_funding(report)
        self.assertEqual(box.ezpass.by_id["EZ-1"].balance_cents, 350)
        self.assertFalse(hasattr(box.ezpass, "bank_account"))

    def test_later_trip_can_match_an_earlier_crossing(self):
        box = runner(trips=[])
        box.apply_events([
            {"event_id": "CR", "kind": "crossing", "crossing": Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 180)},
        ])
        self.assertEqual(box.report("GX-1").confirmation_status, SettlementStatus.FAILED_UNRESOLVED.value)
        self.assertEqual(box.payments.charges, {})
        box.apply_events([
            {"event_id": "TR", "kind": "trip_started", "trip": Trip("T-9", "lyft", "V-1", "pm_ok", NOW - timedelta(minutes=15))},
        ])
        report = box.report("GX-1")
        self.assertEqual(report.trip_id, "T-9")
        self.assertEqual(report.confirmation_status, "confirmed_ezpass_credit")
        self.assertEqual(len(box.payments.charges), 1)

    def test_payment_and_credit_confirmations_are_available(self):
        box = runner()
        box.apply_events([
            {"event_id": "CR", "kind": "crossing", "crossing": Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW, 125)},
        ])
        settlement = box.engine.get("GX-1")
        payment = box.payments.confirmation(settlement.passenger_charge_id)
        credit = box.ezpass.confirmation(settlement.ezpass_credit_id)
        self.assertTrue(payment.confirmed and payment.simulated)
        self.assertEqual(payment.method_token, "pm_ok")
        self.assertTrue(credit.confirmed and credit.simulated)
        self.assertEqual(credit.account_id, "EZ-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
