"""Settlement engine. Passenger funds only. Failures stay unresolved."""

from typing import Dict, Optional
from .models import Settlement, SettlementStatus, Crossing
from .ledger import Ledger
from .adapters.base import TripSource, CrossingSource, EzPassDirectory, PassengerPayment


class Engine:
    def __init__(self, trips: TripSource, ezpass: EzPassDirectory, crossings: CrossingSource, payments: PassengerPayment, ledger: Ledger) -> None:
        self.trips = trips
        self.ezpass = ezpass
        self.crossings = crossings
        self.payments = payments
        self.ledger = ledger
        self.settlements: Dict[str, Settlement] = {}

    def ingest(self) -> int:
        count = 0
        for crossing in self.crossings.poll():
            self._open(crossing)
            count += 1
        return count

    def _open(self, crossing: Crossing) -> Settlement:
        existing = self.settlements.get(crossing.crossing_id)
        if existing is not None:
            existing.status = SettlementStatus.DUPLICATE_BLOCKED
            existing.touch()
            self.ledger.append("duplicate_blocked", crossing.crossing_id, "crossing already open", status=existing.status.value)
            return existing
        settlement = Settlement(
            crossing_id=crossing.crossing_id,
            vehicle_id=crossing.vehicle_id,
            crossed_at=crossing.crossed_at,
            status=SettlementStatus.DETECTED,
        )
        self.settlements[crossing.crossing_id] = settlement
        self.ledger.append("crossing_detected", crossing.crossing_id, f"{crossing.gantry} vehicle {crossing.vehicle_id}", status=settlement.status.value)
        trip = self.trips.find_trip_for_vehicle(crossing.vehicle_id, crossing.crossed_at)
        if trip is None:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "no single active passenger trip"
            settlement.touch()
            self.ledger.append("match_failed", crossing.crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        account = self.ezpass.account_for_vehicle(crossing.vehicle_id)
        if account is None:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "no vehicle E-ZPass account"
            settlement.trip_id = trip.trip_id
            settlement.touch()
            self.ledger.append("ezpass_missing", crossing.crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        settlement.trip_id = trip.trip_id
        settlement.tnc = trip.tnc
        settlement.ezpass_account_id = account.account_id
        settlement.status = SettlementStatus.MATCHED
        settlement.touch()
        self.ledger.append("matched", crossing.crossing_id, f"trip {trip.trip_id} ezpass {account.account_id} ending {account.last4}", status=settlement.status.value)
        if crossing.official_amount_cents is None:
            settlement.status = SettlementStatus.AWAITING_OFFICIAL_AMOUNT
            settlement.touch()
            self.ledger.append("awaiting_amount", crossing.crossing_id, "official post not yet available", status=settlement.status.value)
        else:
            self._settle(settlement, crossing.official_amount_cents, trip.passenger_method_token)
        return settlement

    def apply_official_posts(self) -> int:
        applied = 0
        for crossing_id, settlement in list(self.settlements.items()):
            if settlement.status != SettlementStatus.AWAITING_OFFICIAL_AMOUNT:
                continue
            amount = self.crossings.official_amount(crossing_id)
            if amount is None:
                continue
            trip = self.trips.find_trip_for_vehicle(settlement.vehicle_id, settlement.crossed_at)
            if trip is None:
                settlement.status = SettlementStatus.FAILED_UNRESOLVED
                settlement.failure_reason = "trip no longer matchable at official post"
                settlement.touch()
                self.ledger.append("post_unresolved", crossing_id, settlement.failure_reason, status=settlement.status.value)
                continue
            self._settle(settlement, amount, trip.passenger_method_token)
            applied += 1
        return applied

    def _settle(self, settlement: Settlement, amount_cents: int, method_token: str) -> None:
        if settlement.passenger_charge_id or settlement.status in {SettlementStatus.CREDITED_TO_EZPASS, SettlementStatus.RECONCILED, SettlementStatus.REFUNDED}:
            self.ledger.append("duplicate_blocked", settlement.crossing_id, "settlement already charged", status=SettlementStatus.DUPLICATE_BLOCKED.value)
            return
        settlement.amount_cents = amount_cents
        settlement.status = SettlementStatus.PASSENGER_CHARGE_PENDING
        settlement.touch()
        try:
            charge_id = self.payments.charge(method_token, amount_cents, settlement.crossing_id)
        except Exception as exc:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = f"passenger charge failed: {exc}"
            settlement.touch()
            self.ledger.append("charge_failed", settlement.crossing_id, settlement.failure_reason, amount_cents, settlement.status.value)
            return
        settlement.passenger_charge_id = charge_id
        settlement.status = SettlementStatus.PASSENGER_CHARGED
        settlement.touch()
        self.ledger.append("passenger_charged", settlement.crossing_id, charge_id, amount_cents, settlement.status.value)
        try:
            credit_id = self.ezpass.credit(settlement.ezpass_account_id, amount_cents, settlement.crossing_id)
        except Exception as exc:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = f"ezpass credit failed after passenger charge: {exc}"
            settlement.touch()
            self.ledger.append("credit_failed", settlement.crossing_id, settlement.failure_reason, amount_cents, settlement.status.value)
            return
        settlement.ezpass_credit_id = credit_id
        settlement.status = SettlementStatus.CREDITED_TO_EZPASS
        settlement.touch()
        self.ledger.append("credited_to_ezpass", settlement.crossing_id, credit_id, amount_cents, settlement.status.value)
        settlement.status = SettlementStatus.RECONCILED
        settlement.touch()
        self.ledger.append("reconciled", settlement.crossing_id, f"charge {charge_id} credit {credit_id}", amount_cents, settlement.status.value)

    def refund(self, crossing_id: str) -> Settlement:
        settlement = self.settlements[crossing_id]
        if not settlement.passenger_charge_id:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "nothing to refund"
            settlement.touch()
            return settlement
        self.payments.refund(settlement.passenger_charge_id)
        settlement.status = SettlementStatus.REFUNDED
        settlement.touch()
        self.ledger.append("refunded", crossing_id, settlement.passenger_charge_id, settlement.amount_cents or 0, settlement.status.value)
        return settlement

    def get(self, crossing_id: str) -> Optional[Settlement]:
        return self.settlements.get(crossing_id)
