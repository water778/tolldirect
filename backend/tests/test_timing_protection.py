"""Timing, zero-balance protection, and future-adapter contract tests."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tolldirect.core.timing import PaymentTimingModel, CreditTiming, PaymentStage
from tolldirect.adapters.future import (
    UnimplementedRealAdapter,
    require_trip_source,
    require_crossing_source,
    require_payment_confirmation,
    require_ezpass_confirmation,
    require_credit_not_implied_by_authorization,
    AdapterContractError,
)
from tolldirect.adapters.providers import SyntheticTripProvider, SyntheticCrossingProvider, SyntheticPaymentProvider, SyntheticEzPassProvider
from tolldirect.models import Trip, EzPassAccount


NOW = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
CROSSED = NOW + timedelta(minutes=4)
POSTED = CROSSED + timedelta(days=3)


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.model = PaymentTimingModel()

    def test_authorization_does_not_increase_ezpass_balance(self):
        result = self.model.run("GX-1", 350, 0, NOW, CROSSED, POSTED, CreditTiming.AFTER_OFFICIAL_POST)
        authorized = result.stage_at(PaymentStage.AUTHORIZED)
        captured = result.stage_at(PaymentStage.CAPTURED)
        settled = result.stage_at(PaymentStage.SETTLED)
        self.assertEqual(authorized.ezpass_balance_cents, 0)
        self.assertEqual(captured.ezpass_balance_cents, 0)
        self.assertEqual(settled.ezpass_balance_cents, 0)
        self.assertEqual(result.stage_at(PaymentStage.CONFIRMED_EZPASS_CREDIT).ezpass_balance_cents, 350)
        self.assertFalse(result.realtime_credit_verified)
        self.assertFalse(result.driver_funding_used)

    def test_zero_balance_before_and_at_crossing_are_proposed_not_verified(self):
        before = self.model.run("GX-B", 350, 0, NOW, CROSSED, POSTED, CreditTiming.BEFORE_CROSSING)
        at = self.model.run("GX-A", 350, 0, NOW, CROSSED, POSTED, CreditTiming.AT_CROSSING)
        self.assertFalse(before.exposure.exposed)
        self.assertFalse(at.exposure.exposed)
        self.assertIn("not verified", before.exposure.reason)
        self.assertFalse(before.realtime_credit_verified)
        self.assertFalse(at.realtime_credit_verified)

    def test_credit_after_post_is_exposed_when_balance_is_zero(self):
        result = self.model.run("GX-Z", 350, 0, NOW, CROSSED, POSTED, CreditTiming.AFTER_OFFICIAL_POST)
        self.assertTrue(result.exposure.exposed)
        self.assertGreater(result.exposure.gap, timedelta(0))
        self.assertIn("before the E-ZPass credit", result.exposure.reason)
        self.assertFalse(result.exposure.driver_funding_used)
        self.assertEqual(result.stage_at(PaymentStage.CONFIRMED_EZPASS_CREDIT).at, POSTED + timedelta(days=2))

    def test_positive_balance_is_not_exposed(self):
        result = self.model.run("GX-P", 350, 1000, NOW, CROSSED, POSTED, CreditTiming.AFTER_OFFICIAL_POST)
        self.assertFalse(result.exposure.exposed)

    def test_stages_are_ordered_and_distinct(self):
        result = self.model.run("GX-1", 200, 0, NOW, CROSSED, POSTED, CreditTiming.AFTER_OFFICIAL_POST)
        order = [event.stage for event in result.stages]
        self.assertEqual(order, [
            PaymentStage.AUTHORIZED,
            PaymentStage.CAPTURED,
            PaymentStage.SETTLED,
            PaymentStage.CONFIRMED_EZPASS_CREDIT,
        ])
        times = [event.at for event in result.stages]
        self.assertEqual(times, sorted(times))


    def test_pre_crossing_credit_cannot_precede_capture(self):
        # Crossing one second after approach: capture at +5s is after the gantry.
        crossed = NOW + timedelta(seconds=1)
        result = self.model.run("GX-FAST", 350, 0, NOW, crossed, crossed + timedelta(days=3), CreditTiming.BEFORE_CROSSING)
        self.assertTrue(result.credit_deferred)
        self.assertGreater(result.stage_at(PaymentStage.CONFIRMED_EZPASS_CREDIT).at, crossed)
        self.assertTrue(result.exposure.exposed)
        self.assertFalse(result.realtime_credit_verified)


class FutureAdapterContractTests(unittest.TestCase):
    def test_synthetic_adapters_satisfy_contracts(self):
        trips = SyntheticTripProvider([Trip("T-1", "uber", "V-1", "pm_ok", NOW)])
        crossings = SyntheticCrossingProvider([])
        payments = SyntheticPaymentProvider()
        ezpass = SyntheticEzPassProvider([EzPassAccount("EZ-1", "V-1", "4821", 0)])
        require_trip_source(trips)
        require_crossing_source(crossings)
        require_payment_confirmation(payments)
        require_ezpass_confirmation(ezpass)
        require_credit_not_implied_by_authorization(payments, ezpass)
        charge_id = payments.charge("pm_ok", 100, "GX-1")
        self.assertEqual(ezpass.by_id["EZ-1"].balance_cents, 0)
        credit_id = ezpass.credit("EZ-1", 100, "GX-1")
        self.assertNotEqual(payments.confirmation(charge_id).charge_id, ezpass.confirmation(credit_id).credit_id)

    def test_unimplemented_real_adapter_fails_honestly(self):
        adapter = UnimplementedRealAdapter()
        failures = []
        for call in (
            lambda: adapter.events(),
            lambda: adapter.records(),
            lambda: adapter.charge("pm", 100, "GX"),
            lambda: adapter.credit("EZ-1", 100, "GX"),
            lambda: adapter.confirmation("missing"),
        ):
            try:
                call()
            except NotImplementedError as exc:
                failures.append(str(exc))
        self.assertEqual(len(failures), 5)
        self.assertIn("no authorized trip feed", failures[0])
        self.assertIn("no verified E-ZPass external credit", failures[3])
        self.assertFalse(adapter.realtime_external_credit_supported())
        with self.assertRaises(AdapterContractError):
            require_trip_source(adapter)

    def test_driver_bank_destination_is_rejected(self):
        class BadEzPass(SyntheticEzPassProvider):
            bank_account = "not-permitted"

        with self.assertRaises(AdapterContractError):
            require_ezpass_confirmation(BadEzPass([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

