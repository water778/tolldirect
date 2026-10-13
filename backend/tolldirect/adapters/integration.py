"""Durable integration runner over provider-independent adapters.

Uses the existing Engine for financial effects. Adds event ordering,
exactly-once claims, insufficient-funds risk, and a transaction report.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..engine import Engine
from ..models import Crossing, Settlement, SettlementStatus
from ..store import Store
from ..core.reconciliation import FundsAssessor
from .providers import (
    SyntheticTripProvider,
    SyntheticCrossingProvider,
    SyntheticPaymentProvider,
    SyntheticEzPassProvider,
)


@dataclass
class TransactionReport:
    crossing_id: str
    trip_id: Optional[str]
    passenger_charge_id: Optional[str]
    destination_kind: str
    ezpass_account_id: Optional[str]
    ezpass_last4: Optional[str]
    amount_cents: Optional[int]
    confirmation_status: str
    funds_risk: str
    driver_funding_used: bool
    simulation_only: bool
    audit_trail: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "crossing_id": self.crossing_id,
            "trip_id": self.trip_id,
            "passenger_charge_id": self.passenger_charge_id,
            "destination_kind": self.destination_kind,
            "ezpass_account_id": self.ezpass_account_id,
            "ezpass_last4": self.ezpass_last4,
            "amount_cents": self.amount_cents,
            "confirmation_status": self.confirmation_status,
            "funds_risk": self.funds_risk,
            "driver_funding_used": self.driver_funding_used,
            "simulation_only": self.simulation_only,
            "audit_trail": self.audit_trail,
        }


class IntegrationRunner:
    """Applies provider events without changing the core settlement rules."""

    def __init__(
        self,
        trips: SyntheticTripProvider,
        crossings: SyntheticCrossingProvider,
        payments: SyntheticPaymentProvider,
        ezpass: SyntheticEzPassProvider,
        store: Store,
    ) -> None:
        self.trips = trips
        self.crossings = crossings
        self.payments = payments
        self.ezpass = ezpass
        self.store = store
        self.engine = Engine(trips, ezpass, crossings, payments, store)
        self.funds = FundsAssessor()
        self.funds_risk: Dict[str, str] = {}
        self._seen_events = set()

    def apply_events(self, events: List[dict]) -> int:
        """Apply events in the given order, including out-of-order records."""
        applied = 0
        for event in events:
            event_id = event["event_id"]
            if event_id in self._seen_events or not self.store.claim(f"event:{event_id}", event["kind"]):
                continue
            self._seen_events.add(event_id)
            self._apply(event)
            applied += 1
        return applied

    def _apply(self, event: dict) -> None:
        kind = event["kind"]
        if kind == "trip_started":
            self.trips.add_trip(event["trip"])
            self._retry_unmatched()
        elif kind == "crossing":
            crossing = event["crossing"]
            self._note_funds(crossing)
            self.crossings._queue.append(crossing)
            self.engine.ingest()
        elif kind == "official_amount":
            self.crossings.post_official_amount(event["crossing_id"], event["amount_cents"])
            self.engine.apply_official_posts()
        elif kind == "retry":
            self.engine.retry(event["crossing_id"])
        elif kind == "refund":
            self.engine.refund(event["crossing_id"])
        elif kind == "adjustment":
            self.engine.apply_commercial_adjustment(event["crossing_id"], event["new_total_cents"])

    def _note_funds(self, crossing: Crossing) -> None:
        account = self.ezpass.account_for_vehicle(crossing.vehicle_id)
        if account is None:
            return
        assessment = self.funds.assess(account.balance_cents)
        self.funds_risk[crossing.crossing_id] = assessment.risk

    def _retry_unmatched(self) -> None:
        for settlement in self.store.all_settlements():
            if settlement.failure_reason != "no single active passenger trip":
                continue
            # A later trip event can match a previously unmatched crossing once.
            if not self.store.claim(f"rematch:{settlement.crossing_id}", "rematch"):
                continue
            self.store.conn.execute("DELETE FROM settlements WHERE crossing_id=?", (settlement.crossing_id,))
            self.store.conn.execute("DELETE FROM idempotency WHERE key=?", (f"open:{settlement.crossing_id}",))
            self.store.conn.commit()
            self.engine.settlements.pop(settlement.crossing_id, None)
            crossing = self.crossings._seen.get(settlement.crossing_id)
            if crossing is not None:
                self.crossings._queue.append(crossing)
                self.engine.ingest()

    def report(self, crossing_id: str) -> TransactionReport:
        settlement = self.engine.get(crossing_id)
        account = None
        if settlement and settlement.ezpass_account_id:
            account = self.ezpass.by_id.get(settlement.ezpass_account_id)
        charge_confirmed = False
        credit_confirmed = False
        if settlement and settlement.passenger_charge_id:
            confirmation = self.payments.confirmation(settlement.passenger_charge_id)
            charge_confirmed = bool(confirmation and confirmation.confirmed)
        if settlement and settlement.ezpass_credit_id:
            confirmation = self.ezpass.confirmation(settlement.ezpass_credit_id)
            credit_confirmed = bool(confirmation and confirmation.confirmed)
        if settlement is None:
            status = "missing"
        elif settlement.status is SettlementStatus.RECONCILED and charge_confirmed and credit_confirmed:
            status = "confirmed_ezpass_credit"
        elif settlement.status is SettlementStatus.REFUNDED:
            status = "refunded"
        elif settlement.passenger_charge_id and not settlement.ezpass_credit_id:
            status = "charged_pending_credit"
        else:
            status = settlement.status.value
        trail = [entry.kind for entry in self.store.ledger() if entry.crossing_id == crossing_id]
        return TransactionReport(
            crossing_id=crossing_id,
            trip_id=settlement.trip_id if settlement else None,
            passenger_charge_id=settlement.passenger_charge_id if settlement else None,
            destination_kind="ezpass_account",
            ezpass_account_id=settlement.ezpass_account_id if settlement else None,
            ezpass_last4=account.last4 if account else None,
            amount_cents=settlement.amount_cents if settlement else None,
            confirmation_status=status,
            funds_risk=self.funds_risk.get(crossing_id, "none"),
            driver_funding_used=False,
            simulation_only=True,
            audit_trail=trail,
        )

    def assert_no_driver_funding(self, report: TransactionReport) -> None:
        if report.driver_funding_used:
            raise AssertionError("driver funding is not permitted")
        if report.destination_kind != "ezpass_account":
            raise AssertionError("destination must be the vehicle E-ZPass account")
        forbidden = ("bank", "iban", "routing_number", "driver_recharge")
        blob = " ".join(str(value).lower() for value in report.to_dict().values() if not isinstance(value, list))
        if any(word in blob for word in forbidden):
            raise AssertionError("driver bank or recharge field found in report")
