"""Tests for matching, toll verification, routing, and reconciliation modules."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tolldirect.models import Trip, Crossing, EzPassAccount, Settlement, SettlementStatus
from tolldirect.core import (
    TripTollMatcher,
    MatchOutcome,
    TollVerifier,
    TollStatus,
    PaymentRouter,
    EzPassDestination,
    RouteStatus,
    RouteMode,
    Reconciler,
    FundsAssessor,
    LifecyclePhase,
    RoutingCoordinator,
)


NOW = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.matcher = TripTollMatcher()
        self.trips = [
            Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=30)),
            Trip("T-2", "lyft", "V-2", "pm_2", NOW - timedelta(minutes=10), NOW + timedelta(minutes=20)),
        ]

    def test_exact_vehicle_and_window_matches(self):
        crossing = Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW - timedelta(minutes=5))
        result = self.matcher.match(crossing, self.trips)
        self.assertTrue(result.matched)
        self.assertEqual(result.trip.trip_id, "T-1")
        self.assertEqual(result.outcome, MatchOutcome.MATCHED)

    def test_no_trip_is_not_invented(self):
        crossing = Crossing("GX-9", "V-9", "MA9", "TAG9", "Callahan", NOW)
        result = self.matcher.match(crossing, self.trips)
        self.assertEqual(result.outcome, MatchOutcome.NONE)
        self.assertIsNone(result.trip)

    def test_overlapping_trips_are_ambiguous_and_not_charged(self):
        trips = [
            Trip("T-A", "uber", "V-1", "pm_a", NOW - timedelta(minutes=40)),
            Trip("T-B", "lyft", "V-1", "pm_b", NOW - timedelta(minutes=15)),
        ]
        crossing = Crossing("GX-O", "V-1", "MA1", "TAG1", "Tobin", NOW)
        result = self.matcher.match(crossing, trips)
        self.assertEqual(result.outcome, MatchOutcome.AMBIGUOUS)
        self.assertEqual(len(result.candidates), 2)

    def test_ended_trip_is_not_matched(self):
        trips = [Trip("T-X", "uber", "V-1", "pm_ok", NOW - timedelta(hours=2), NOW - timedelta(hours=1))]
        crossing = Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW)
        self.assertEqual(self.matcher.match(crossing, trips).outcome, MatchOutcome.NONE)


class TollTests(unittest.TestCase):
    def setUp(self):
        self.verifier = TollVerifier()

    def test_missing_official_amount_is_pending_not_invented(self):
        result = self.verifier.verify(None)
        self.assertEqual(result.status, TollStatus.PENDING_OFFICIAL)
        self.assertIsNone(result.amount_cents)
        self.assertFalse(result.invented)

    def test_recorded_amount_is_accepted(self):
        result = self.verifier.verify(350)
        self.assertEqual(result.status, TollStatus.VERIFIED)
        self.assertEqual(result.amount_cents, 350)

    def test_zero_or_negative_is_invalid(self):
        self.assertEqual(self.verifier.verify(0).status, TollStatus.INVALID)
        self.assertEqual(self.verifier.verify(-10).status, TollStatus.INVALID)

    def test_commercial_adjustment_is_delta_only(self):
        result = self.verifier.commercial_delta(300, 450)
        self.assertEqual(result.status, TollStatus.ADJUSTMENT_DELTA)
        self.assertEqual(result.delta_cents, 150)
        self.assertEqual(result.amount_cents, 450)

    def test_non_positive_adjustment_is_rejected(self):
        self.assertEqual(self.verifier.commercial_delta(300, 300).status, TollStatus.INVALID)
        self.assertEqual(self.verifier.commercial_delta(300, 200).status, TollStatus.INVALID)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = PaymentRouter()
        self.destination = EzPassDestination("EZ-1", "V-1", "4821")

    def test_plan_routes_to_ezpass_not_a_bank(self):
        plan = self.router.plan("GX-1", 350, "pm_ok", self.destination)
        self.assertEqual(plan.status, RouteStatus.PLANNED)
        self.assertEqual(plan.destination.kind.value, "ezpass_account")
        self.assertFalse(plan.driver_funding_used)
        self.assertEqual(plan.mode, RouteMode.SIMULATED)
        self.assertFalse(hasattr(plan.destination, "bank_account"))

    def test_simulated_charge_is_not_confirmed_until_credit_id(self):
        plan = self.router.plan("GX-1", 350, "pm_ok", self.destination)
        plan.mark_simulated_charge("PCH-0001")
        self.assertEqual(plan.status, RouteStatus.SIMULATED_CHARGED)
        with self.assertRaises(ValueError):
            plan.confirm()
        plan.mark_simulated_credit("EZC-0001")
        plan.confirm()
        self.assertEqual(plan.mode, RouteMode.CONFIRMED_CREDIT)
        self.assertEqual(plan.status, RouteStatus.CONFIRMED)

    def test_missing_method_or_amount_is_rejected(self):
        self.assertEqual(self.router.plan("GX-1", 0, "pm_ok", self.destination).status, RouteStatus.REJECTED)
        self.assertEqual(self.router.plan("GX-1", 350, "", self.destination).status, RouteStatus.REJECTED)

    def test_non_ezpass_destination_is_refused(self):
        with self.assertRaises(TypeError):
            self.router.plan("GX-1", 350, "pm_ok", object())


class ReconciliationTests(unittest.TestCase):
    def test_phases_and_balance(self):
        reconciler = Reconciler()
        reconciled = Settlement(
            "GX-1", "V-1", NOW, SettlementStatus.RECONCILED,
            trip_id="T-1", ezpass_account_id="EZ-1", amount_cents=350,
            passenger_charge_id="PCH-1", ezpass_credit_id="EZC-1",
        )
        unmatched = Settlement(
            "GX-9", "V-9", NOW, SettlementStatus.FAILED_UNRESOLVED,
            failure_reason="no single active passenger trip",
        )
        pending_credit = Settlement(
            "GX-2", "V-2", NOW, SettlementStatus.PASSENGER_CHARGED,
            amount_cents=200, passenger_charge_id="PCH-2",
        )
        report = reconciler.report([reconciled, unmatched, pending_credit])
        self.assertEqual(reconciler.classify(reconciled), LifecyclePhase.RECONCILED)
        self.assertEqual(reconciler.classify(unmatched), LifecyclePhase.UNMATCHED)
        self.assertEqual(reconciler.classify(pending_credit), LifecyclePhase.CHARGED_PENDING_CREDIT)
        self.assertIn("GX-9", report.unmatched)
        self.assertIn("GX-2", report.unresolved)
        self.assertFalse(report.balanced)
        self.assertTrue(report.simulation_only)

    def test_dispute_overrides_phase(self):
        reconciler = Reconciler()
        settlement = Settlement("GX-1", "V-1", NOW, SettlementStatus.RECONCILED, amount_cents=100, passenger_charge_id="P", ezpass_credit_id="E")
        reconciler.open_dispute("GX-1", "commercial rate dispute")
        self.assertEqual(reconciler.classify(settlement), LifecyclePhase.DISPUTED)
        self.assertIn("GX-1", reconciler.report([settlement]).disputed)

    def test_insufficient_funds_does_not_use_driver(self):
        assessor = FundsAssessor()
        risk = assessor.assess(0)
        self.assertEqual(risk.risk, "insufficient_at_travel")
        self.assertFalse(risk.driver_funding_used)
        self.assertIn("No grace period", risk.note)
        self.assertEqual(assessor.assess(100).risk, "none")

    def test_refunded_is_excluded_from_balance(self):
        reconciler = Reconciler()
        refunded = Settlement(
            "GX-1", "V-1", NOW, SettlementStatus.REFUNDED,
            amount_cents=350, passenger_charge_id="PCH-1", ezpass_credit_id="EZC-1",
        )
        report = reconciler.report([refunded])
        self.assertEqual(report.charged_cents, 0)
        self.assertEqual(report.credited_cents, 0)
        self.assertEqual(report.refunded_cents, 350)
        self.assertTrue(report.balanced)


class CoordinatorTests(unittest.TestCase):
    def test_full_decision_is_simulated_until_confirmed(self):
        coordinator = RoutingCoordinator()
        crossing = Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW)
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20))]
        account = EzPassAccount("EZ-1", "V-1", "4821", 1000)
        decision = coordinator.decide(crossing, trips, account, 350)
        self.assertTrue(decision.simulated)
        self.assertFalse(decision.confirmed)
        self.assertEqual(decision.route.destination.account_id, "EZ-1")
        self.assertEqual(decision.settlement_status, SettlementStatus.PASSENGER_CHARGE_PENDING.value)
        decision.route.mark_simulated_charge("PCH-1")
        self.assertFalse(decision.confirmed)
        decision.route.mark_simulated_credit("EZC-1")
        decision.route.confirm()
        decision.confirmed = True
        self.assertTrue(decision.confirmed)

    def test_delayed_post_waits_and_does_not_invent(self):
        coordinator = RoutingCoordinator()
        crossing = Crossing("GX-1", "V-1", "MA1", "TAG1", "Tobin", NOW)
        trips = [Trip("T-1", "uber", "V-1", "pm_ok", NOW - timedelta(minutes=20))]
        account = EzPassAccount("EZ-1", "V-1", "4821", 1000)
        decision = coordinator.decide(crossing, trips, account, None)
        self.assertEqual(decision.toll_status, TollStatus.PENDING_OFFICIAL.value)
        self.assertIsNone(decision.route)
        self.assertEqual(decision.settlement_status, SettlementStatus.AWAITING_OFFICIAL_AMOUNT.value)

    def test_unmatched_and_ambiguous_produce_no_route(self):
        coordinator = RoutingCoordinator()
        account = EzPassAccount("EZ-1", "V-1", "4821", 1000)
        none = coordinator.decide(Crossing("GX-9", "V-9", "MA9", "TAG9", "Callahan", NOW), [], account, 100)
        self.assertIsNone(none.route)
        trips = [
            Trip("T-A", "uber", "V-1", "pm_a", NOW - timedelta(minutes=30)),
            Trip("T-B", "lyft", "V-1", "pm_b", NOW - timedelta(minutes=10)),
        ]
        ambiguous = coordinator.decide(Crossing("GX-O", "V-1", "MA1", "TAG1", "Tobin", NOW), trips, account, 100)
        self.assertIsNone(ambiguous.route)
        self.assertEqual(ambiguous.match_outcome, MatchOutcome.AMBIGUOUS.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
