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
        self.duplicates_blocked = 0

    def ingest(self) -> int:
        count = 0
        for crossing in self.crossings.poll():
            self._open(crossing)
            count += 1
        return count

    def _open(self, crossing: Crossing) -> Settlement:
        existing = self.settlements.get(crossing.crossing_id)
        if existing is not None:
            self.duplicates_blocked += 1
            self.ledger.append("duplicate_blocked", crossing.crossing_id, "crossing already open; original left unchanged", status=existing.status.value)
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
        settlement.passenger_method_token = trip.passenger_method_token
        settlement.status = SettlementStatus.MATCHED
        settlement.touch()
        self.ledger.append("matched", crossing.crossing_id, f"trip {trip.trip_id} ezpass {account.account_id} ending {account.last4}", status=settlement.status.value)
        if crossing.official_amount_cents is None:
            settlement.status = SettlementStatus.AWAITING_OFFICIAL_AMOUNT
            settlement.touch()
            self.ledger.append("awaiting_amount", crossing.crossing_id, "official post not yet available", status=settlement.status.value)
        else:
            self._settle(settlement, crossing.official_amount_cents)
        return settlement

    def apply_official_posts(self) -> int:
        applied = 0
        for crossing_id, settlement in list(self.settlements.items()):
            if settlement.status != SettlementStatus.AWAITING_OFFICIAL_AMOUNT:
                continue
            amount = self.crossings.official_amount(crossing_id)
            if amount is None:
                continue
            self._settle(settlement, amount)
            applied += 1
        return applied

    def _settle(self, settlement: Settlement, amount_cents: int) -> None:
        if settlement.passenger_charge_id or settlement.status in {SettlementStatus.CREDITED_TO_EZPASS, SettlementStatus.RECONCILED, SettlementStatus.REFUNDED}:
            self.ledger.append("duplicate_blocked", settlement.crossing_id, "settlement already charged", status=settlement.status.value)
            return
        if not settlement.passenger_method_token or not settlement.ezpass_account_id:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "missing passenger method or E-ZPass account"
            settlement.touch()
            self.ledger.append("settle_blocked", settlement.crossing_id, settlement.failure_reason, status=settlement.status.value)
            return
        settlement.amount_cents = amount_cents
        settlement.status = SettlementStatus.PASSENGER_CHARGE_PENDING
        settlement.touch()
        try:
            charge_id = self.payments.charge(settlement.passenger_method_token, amount_cents, settlement.crossing_id)
        except Exception as exc:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = f"passenger charge failed: {exc}"
            settlement.touch()
            self.ledger.append("charge_failed", settlement.crossing_id, settlement.failure_reason, amount_cents, settlement.status.value)
            return
        settlement.passenger_charge_id = charge_id
        settlement.status = SettlementStatus.PASSENGER_CHARGED
        settlement.failure_reason = None
        settlement.touch()
        self.ledger.append("passenger_charged", settlement.crossing_id, charge_id, amount_cents, settlement.status.value)
        self._credit(settlement, amount_cents)

    def _credit(self, settlement: Settlement, amount_cents: int) -> None:
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
        if settlement.amount_cents == amount_cents and settlement.passenger_charge_id:
            settlement.status = SettlementStatus.RECONCILED
            settlement.failure_reason = None
            settlement.touch()
            self.ledger.append("reconciled", settlement.crossing_id, f"charge {settlement.passenger_charge_id} credit {credit_id}", amount_cents, settlement.status.value)

    def retry(self, crossing_id: str) -> Settlement:
        settlement = self.settlements[crossing_id]
        settlement.retry_count += 1
        self.ledger.append("retry", crossing_id, f"attempt {settlement.retry_count}", status=settlement.status.value)
        if settlement.passenger_charge_id and not settlement.ezpass_credit_id:
            self._credit(settlement, settlement.amount_cents or 0)
            return settlement
        if settlement.passenger_charge_id:
            self.ledger.append("retry_blocked", crossing_id, "already charged; no second passenger charge", status=settlement.status.value)
            return settlement
        if settlement.status != SettlementStatus.FAILED_UNRESOLVED or not settlement.passenger_method_token:
            self.ledger.append("retry_blocked", crossing_id, "not retryable", status=settlement.status.value)
            return settlement
        amount = settlement.amount_cents or self.crossings.official_amount(crossing_id)
        if amount is None:
            settlement.failure_reason = "retry waiting for official amount"
            self.ledger.append("retry_blocked", crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        self._settle(settlement, amount)
        return settlement

    def apply_commercial_adjustment(self, crossing_id: str, new_total_cents: int) -> Settlement:
        settlement = self.settlements[crossing_id]
        if settlement.status not in {SettlementStatus.RECONCILED, SettlementStatus.CREDITED_TO_EZPASS}:
            settlement.failure_reason = "adjustment requires a confirmed credit"
            self.ledger.append("adjustment_blocked", crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        delta = new_total_cents - (settlement.amount_cents or 0)
        if delta == 0:
            self.ledger.append("adjustment_noop", crossing_id, "no difference", status=settlement.status.value)
            return settlement
        if delta > 0:
            charge_id = self.payments.charge(settlement.passenger_method_token, delta, crossing_id + ":adj")
            self.ezpass.credit(settlement.ezpass_account_id, delta, crossing_id + ":adj")
            self.ledger.append("commercial_adjustment", crossing_id, f"delta charge {charge_id}", delta, settlement.status.value)
        else:
            settlement.failure_reason = "negative adjustment not auto-applied; remains visible for review"
            self.ledger.append("adjustment_blocked", crossing_id, settlement.failure_reason, delta, settlement.status.value)
            return settlement
        settlement.adjustment_cents += delta
        settlement.amount_cents = new_total_cents
        settlement.touch()
        return settlement

    def refund(self, crossing_id: str) -> Settlement:
        settlement = self.settlements[crossing_id]
        if not settlement.passenger_charge_id:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "nothing to refund"
            settlement.touch()
            self.ledger.append("refund_blocked", crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        self.payments.refund(settlement.passenger_charge_id)
        if settlement.ezpass_credit_id and settlement.amount_cents:
            self.ezpass.reverse_credit(settlement.ezpass_account_id, settlement.amount_cents, crossing_id)
        settlement.status = SettlementStatus.REFUNDED
        settlement.touch()
        self.ledger.append("refunded", crossing_id, settlement.passenger_charge_id, settlement.amount_cents or 0, settlement.status.value)
        return settlement

    def reconcile(self) -> dict:
        charged = 0
        credited = 0
        unresolved = []
        for s in self.settlements.values():
            if s.passenger_charge_id and s.status != SettlementStatus.REFUNDED:
                charged += s.amount_cents or 0
            if s.ezpass_credit_id and s.status != SettlementStatus.REFUNDED:
                credited += s.amount_cents or 0
            if s.status == SettlementStatus.FAILED_UNRESOLVED:
                unresolved.append(s.crossing_id)
            if s.status == SettlementStatus.RECONCILED and not (s.passenger_charge_id and s.ezpass_credit_id):
                raise AssertionError(f"{s.crossing_id} reconciled without both ids")
        report = {
            "charged_cents": charged,
            "credited_cents": credited,
            "unresolved": unresolved,
            "duplicates_blocked": self.duplicates_blocked,
            "balanced": charged == credited,
        }
        self.ledger.append("reconciliation_report", "*", str(report), charged - credited, "reconciled" if report["balanced"] else "unbalanced")
        return report

    def get(self, crossing_id: str) -> Optional[Settlement]:
        return self.settlements.get(crossing_id)
