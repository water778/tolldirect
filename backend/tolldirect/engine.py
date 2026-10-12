"""Settlement engine. Passenger funds only. Durable and idempotent."""

from typing import Dict, Optional
from .models import Settlement, SettlementStatus, Crossing, LedgerEntry, utcnow
from .store import Store
from .adapters.base import TripSource, CrossingSource, EzPassDirectory, PassengerPayment


class Engine:
    def __init__(self, trips: TripSource, ezpass: EzPassDirectory, crossings: CrossingSource, payments: PassengerPayment, store: Store) -> None:
        self.trips = trips
        self.ezpass = ezpass
        self.crossings = crossings
        self.payments = payments
        self.store = store
        self.settlements: Dict[str, Settlement] = {s.crossing_id: s for s in store.all_settlements()}
        self.duplicates_blocked = 0

    def ingest(self) -> int:
        count = 0
        for crossing in self.crossings.poll():
            self._open(crossing)
            count += 1
        return count

    def _persist(self, settlement: Settlement) -> None:
        settlement.touch()
        self.settlements[settlement.crossing_id] = settlement
        self.store.save(settlement)

    def _log(self, kind: str, crossing_id: str, detail: str, amount_cents: int = 0, status: str = "") -> None:
        entry = LedgerEntry(self.store.next_ledger_id(), utcnow(), kind, crossing_id, detail, amount_cents, status)
        self.store.append_ledger(entry)

    def _open(self, crossing: Crossing) -> Settlement:
        existing = self.store.get(crossing.crossing_id)
        if existing is not None:
            self.duplicates_blocked += 1
            self._log("duplicate_blocked", crossing.crossing_id, "crossing already open; original left unchanged", status=existing.status.value)
            self.settlements[crossing.crossing_id] = existing
            return existing
        if not self.store.claim(f"open:{crossing.crossing_id}", "opened"):
            self.duplicates_blocked += 1
            self._log("duplicate_blocked", crossing.crossing_id, "concurrent open rejected", status="duplicate_blocked")
            return self.store.get(crossing.crossing_id) or Settlement(crossing_id=crossing.crossing_id, status=SettlementStatus.DUPLICATE_BLOCKED)
        settlement = Settlement(crossing_id=crossing.crossing_id, vehicle_id=crossing.vehicle_id, crossed_at=crossing.crossed_at)
        self._persist(settlement)
        self._log("crossing_detected", crossing.crossing_id, f"{crossing.gantry} vehicle {crossing.vehicle_id}", status=settlement.status.value)
        trip = self.trips.find_trip_for_vehicle(crossing.vehicle_id, crossing.crossed_at)
        if trip is None:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "no single active passenger trip"
            self._persist(settlement)
            self._log("match_failed", crossing.crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        account = self.ezpass.account_for_vehicle(crossing.vehicle_id)
        if account is None:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "no vehicle E-ZPass account"
            settlement.trip_id = trip.trip_id
            self._persist(settlement)
            self._log("ezpass_missing", crossing.crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        settlement.trip_id = trip.trip_id
        settlement.tnc = trip.tnc
        settlement.ezpass_account_id = account.account_id
        settlement.passenger_method_token = trip.passenger_method_token
        settlement.status = SettlementStatus.MATCHED
        self._persist(settlement)
        self._log("matched", crossing.crossing_id, f"trip {trip.trip_id} ezpass {account.account_id} ending {account.last4}", status=settlement.status.value)
        if crossing.official_amount_cents is None:
            settlement.status = SettlementStatus.AWAITING_OFFICIAL_AMOUNT
            self._persist(settlement)
            self._log("awaiting_amount", crossing.crossing_id, "official post not yet available", status=settlement.status.value)
        else:
            self._settle(settlement, crossing.official_amount_cents)
        return settlement

    def apply_official_posts(self) -> int:
        applied = 0
        for settlement in list(self.settlements.values()):
            if settlement.status != SettlementStatus.AWAITING_OFFICIAL_AMOUNT:
                continue
            amount = self.crossings.official_amount(settlement.crossing_id)
            if amount is None:
                continue
            self._settle(settlement, amount)
            applied += 1
        return applied

    def _settle(self, settlement: Settlement, amount_cents: int) -> None:
        if settlement.passenger_charge_id or settlement.status in {SettlementStatus.PASSENGER_CHARGED, SettlementStatus.CREDITED_TO_EZPASS, SettlementStatus.RECONCILED, SettlementStatus.REFUNDED}:
            self._log("duplicate_blocked", settlement.crossing_id, "already charged; no automatic second charge", status=settlement.status.value)
            return
        if not settlement.passenger_method_token or not settlement.ezpass_account_id:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "missing passenger method or E-ZPass account"
            self._persist(settlement)
            self._log("settle_blocked", settlement.crossing_id, settlement.failure_reason, status=settlement.status.value)
            return
        settlement.amount_cents = amount_cents
        settlement.status = SettlementStatus.PASSENGER_CHARGE_PENDING
        self._persist(settlement)
        if not self.store.claim(f"charge:{settlement.crossing_id}", "charging"):
            self._log("duplicate_blocked", settlement.crossing_id, "charge already claimed", status=settlement.status.value)
            return
        try:
            charge_id = self.payments.charge(settlement.passenger_method_token, amount_cents, settlement.crossing_id)
        except Exception as exc:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = f"passenger charge failed: {exc}"
            self._persist(settlement)
            self._log("charge_failed", settlement.crossing_id, settlement.failure_reason, amount_cents, settlement.status.value)
            return
        settlement.passenger_charge_id = charge_id
        settlement.status = SettlementStatus.PASSENGER_CHARGED
        settlement.failure_reason = None
        self._persist(settlement)
        self._log("passenger_charged", settlement.crossing_id, charge_id, amount_cents, settlement.status.value)
        self._credit(settlement, amount_cents)

    def _credit(self, settlement: Settlement, amount_cents: int) -> None:
        if settlement.ezpass_credit_id:
            return
        if not self.store.claim(f"credit:{settlement.crossing_id}", "crediting"):
            self._log("duplicate_blocked", settlement.crossing_id, "credit already claimed", status=settlement.status.value)
            return
        try:
            credit_id = self.ezpass.credit(settlement.ezpass_account_id, amount_cents, settlement.crossing_id)
        except Exception as exc:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = f"ezpass credit failed after passenger charge: {exc}"
            self._persist(settlement)
            self._log("credit_failed", settlement.crossing_id, settlement.failure_reason, amount_cents, settlement.status.value)
            return
        settlement.ezpass_credit_id = credit_id
        settlement.status = SettlementStatus.CREDITED_TO_EZPASS
        self._persist(settlement)
        self._log("credited_to_ezpass", settlement.crossing_id, credit_id, amount_cents, settlement.status.value)
        if settlement.passenger_charge_id:
            settlement.status = SettlementStatus.RECONCILED
            settlement.failure_reason = None
            self._persist(settlement)
            self._log("reconciled", settlement.crossing_id, f"charge {settlement.passenger_charge_id} credit {credit_id}", amount_cents, settlement.status.value)

    def retry(self, crossing_id: str) -> Settlement:
        settlement = self.store.get(crossing_id)
        settlement.retry_count += 1
        self._persist(settlement)
        self._log("retry", crossing_id, f"attempt {settlement.retry_count}", status=settlement.status.value)
        if settlement.passenger_charge_id and not settlement.ezpass_credit_id:
            self.store.conn.execute("DELETE FROM idempotency WHERE key=?", (f"credit:{crossing_id}",))
            self.store.conn.commit()
            self._credit(settlement, settlement.amount_cents or 0)
            return self.store.get(crossing_id)
        if settlement.passenger_charge_id:
            self._log("retry_blocked", crossing_id, "already charged; no second passenger charge", status=settlement.status.value)
            return settlement
        if settlement.status != SettlementStatus.FAILED_UNRESOLVED:
            self._log("retry_blocked", crossing_id, "not retryable", status=settlement.status.value)
            return settlement
        amount = settlement.amount_cents or self.crossings.official_amount(crossing_id)
        if amount is None:
            self._log("retry_blocked", crossing_id, "retry waiting for official amount", status=settlement.status.value)
            return settlement
        self.store.conn.execute("DELETE FROM idempotency WHERE key=?", (f"charge:{crossing_id}",))
        self.store.conn.commit()
        self._settle(settlement, amount)
        return self.store.get(crossing_id)

    def apply_commercial_adjustment(self, crossing_id: str, new_total_cents: int) -> Settlement:
        settlement = self.store.get(crossing_id)
        if settlement.status not in {SettlementStatus.RECONCILED, SettlementStatus.CREDITED_TO_EZPASS}:
            self._log("adjustment_blocked", crossing_id, "adjustment requires a confirmed credit", status=settlement.status.value)
            return settlement
        delta = new_total_cents - (settlement.amount_cents or 0)
        key = f"adj:{crossing_id}:{new_total_cents}"
        if not self.store.claim(key, "adjustment"):
            self._log("duplicate_blocked", crossing_id, "adjustment already applied", status=settlement.status.value)
            return settlement
        if delta <= 0:
            self._log("adjustment_blocked", crossing_id, "negative adjustment not auto-applied", delta, settlement.status.value)
            return settlement
        charge_id = self.payments.charge(settlement.passenger_method_token, delta, key)
        self.ezpass.credit(settlement.ezpass_account_id, delta, key)
        settlement.adjustment_cents += delta
        settlement.amount_cents = new_total_cents
        self._persist(settlement)
        self._log("commercial_adjustment", crossing_id, f"delta charge {charge_id}", delta, settlement.status.value)
        return settlement

    def refund(self, crossing_id: str) -> Settlement:
        settlement = self.store.get(crossing_id)
        if not settlement.passenger_charge_id:
            settlement.status = SettlementStatus.FAILED_UNRESOLVED
            settlement.failure_reason = "nothing to refund"
            self._persist(settlement)
            self._log("refund_blocked", crossing_id, settlement.failure_reason, status=settlement.status.value)
            return settlement
        if not self.store.claim(f"refund:{crossing_id}", "refunded"):
            self._log("duplicate_blocked", crossing_id, "refund already claimed", status=settlement.status.value)
            return settlement
        self.payments.refund(settlement.passenger_charge_id)
        if settlement.ezpass_credit_id and settlement.amount_cents:
            self.ezpass.reverse_credit(settlement.ezpass_account_id, settlement.amount_cents, crossing_id)
        settlement.status = SettlementStatus.REFUNDED
        self._persist(settlement)
        self._log("refunded", crossing_id, settlement.passenger_charge_id, settlement.amount_cents or 0, settlement.status.value)
        return settlement

    def reconcile(self) -> dict:
        charged = credited = 0
        unresolved = []
        for s in self.store.all_settlements():
            if s.passenger_charge_id and s.status != SettlementStatus.REFUNDED:
                charged += s.amount_cents or 0
            if s.ezpass_credit_id and s.status != SettlementStatus.REFUNDED:
                credited += s.amount_cents or 0
            if s.status == SettlementStatus.FAILED_UNRESOLVED:
                unresolved.append(s.crossing_id)
        report = {"charged_cents": charged, "credited_cents": credited, "unresolved": unresolved, "duplicates_blocked": self.duplicates_blocked, "balanced": charged == credited}
        self._log("reconciliation_report", "*", str(report), charged - credited, "reconciled" if report["balanced"] else "unbalanced")
        return report

    def get(self, crossing_id: str) -> Optional[Settlement]:
        return self.store.get(crossing_id)
