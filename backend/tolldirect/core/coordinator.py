"""Coordinator that wires matching, verification, routing, and reconciliation.

Simulation only. This does not replace the durable Engine used by existing tests.
"""

from dataclasses import dataclass
from typing import List, Optional

from ..models import Crossing, Trip, EzPassAccount, Settlement, SettlementStatus
from .matching import TripTollMatcher, MatchOutcome
from .toll import TollVerifier, TollStatus
from .routing import PaymentRouter, EzPassDestination, RoutePlan, RouteStatus
from .reconciliation import Reconciler, FundsAssessor


@dataclass
class RoutingDecision:
    crossing_id: str
    match_outcome: str
    toll_status: str
    route: Optional[RoutePlan]
    settlement_status: str
    simulated: bool = True
    confirmed: bool = False
    note: str = ""


class RoutingCoordinator:
    """Proves the routing rules without claiming a real settlement."""

    def __init__(self) -> None:
        self.matcher = TripTollMatcher()
        self.verifier = TollVerifier()
        self.router = PaymentRouter()
        self.reconciler = Reconciler()
        self.funds = FundsAssessor()

    def decide(
        self,
        crossing: Crossing,
        trips: List[Trip],
        account: Optional[EzPassAccount],
        recorded_amount_cents: Optional[int],
    ) -> RoutingDecision:
        match = self.matcher.match(crossing, trips)
        toll = self.verifier.verify(recorded_amount_cents)
        if not match.matched:
            status = (
                SettlementStatus.FAILED_UNRESOLVED.value
                if match.outcome is MatchOutcome.NONE or match.outcome is MatchOutcome.AMBIGUOUS
                else SettlementStatus.FAILED_UNRESOLVED.value
            )
            return RoutingDecision(
                crossing.crossing_id,
                match.outcome.value,
                toll.status.value,
                None,
                status,
                note=match.reason,
            )
        if account is None:
            return RoutingDecision(
                crossing.crossing_id,
                match.outcome.value,
                toll.status.value,
                None,
                SettlementStatus.FAILED_UNRESOLVED.value,
                note="no vehicle E-ZPass account",
            )
        risk = self.funds.assess(account.balance_cents)
        if risk.risk == "insufficient_at_travel":
            self.reconciler.mark_funds_risk(crossing.crossing_id, risk)
        if toll.status is TollStatus.PENDING_OFFICIAL:
            return RoutingDecision(
                crossing.crossing_id,
                match.outcome.value,
                toll.status.value,
                None,
                SettlementStatus.AWAITING_OFFICIAL_AMOUNT.value,
                note=toll.reason,
            )
        if toll.status is not TollStatus.VERIFIED or toll.amount_cents is None:
            return RoutingDecision(
                crossing.crossing_id,
                match.outcome.value,
                toll.status.value,
                None,
                SettlementStatus.FAILED_UNRESOLVED.value,
                note=toll.reason,
            )
        destination = EzPassDestination(account.account_id, account.vehicle_id, account.last4)
        plan = self.router.plan(
            crossing.crossing_id,
            toll.amount_cents,
            match.trip.passenger_method_token,
            destination,
        )
        status = (
            SettlementStatus.PASSENGER_CHARGE_PENDING.value
            if plan.status is RouteStatus.PLANNED
            else SettlementStatus.FAILED_UNRESOLVED.value
        )
        return RoutingDecision(
            crossing.crossing_id,
            match.outcome.value,
            toll.status.value,
            plan,
            status,
            note=plan.reason or risk.note,
        )

    def classify(self, settlement: Settlement) -> str:
        return self.reconciler.classify(settlement).value
