"""Synthetic providers for the four integration contracts. No external calls."""

from typing import Dict, List, Optional
from datetime import datetime

from ..models import Trip, Crossing, EzPassAccount
from .base import TripSource, CrossingSource, EzPassDirectory, PassengerPayment
from .contracts import (
    TripEvent,
    CrossingRecord,
    PaymentConfirmation,
    CreditConfirmation,
    TripEventSource,
    TollCrossingSource,
    PassengerPaymentConfirmation,
    EzPassCreditConfirmation,
)


class SyntheticTripProvider(TripEventSource, TripSource):
    def __init__(self, trips: List[Trip]) -> None:
        self.trips = list(trips)
        self._events = [
            TripEvent(f"TE-{trip.trip_id}", trip, "started", trip.started_at)
            for trip in self.trips
        ]

    def events(self) -> List[TripEvent]:
        return list(self._events)

    def active_trips(self) -> List[Trip]:
        return [trip for trip in self.trips if trip.ended_at is None]

    def find_trip_for_vehicle(self, vehicle_id: str, when: datetime) -> Optional[Trip]:
        matches = [trip for trip in self.trips if trip.vehicle_id == vehicle_id and trip.is_active_at(when)]
        return matches[0] if len(matches) == 1 else None

    def add_trip(self, trip: Trip) -> None:
        self.trips.append(trip)
        self._events.append(TripEvent(f"TE-{trip.trip_id}", trip, "started", trip.started_at))


class SyntheticCrossingProvider(TollCrossingSource, CrossingSource):
    def __init__(self, crossings: List[Crossing], delayed: Optional[Dict[str, int]] = None) -> None:
        self._queue = list(crossings)
        self._seen: Dict[str, Crossing] = {}
        self.delayed = dict(delayed or {})
        self._records = [CrossingRecord(f"CR-{c.crossing_id}", c) for c in crossings]

    def records(self) -> List[CrossingRecord]:
        return list(self._records)

    def poll(self) -> List[Crossing]:
        batch, self._queue = self._queue, []
        for crossing in batch:
            self._seen[crossing.crossing_id] = crossing
        return batch

    def official_amount(self, crossing_id: str) -> Optional[int]:
        crossing = self._seen.get(crossing_id)
        if crossing and crossing.official_amount_cents is not None:
            return crossing.official_amount_cents
        return self.delayed.get(crossing_id)

    def post_official_amount(self, crossing_id: str, amount_cents: int) -> None:
        self.delayed[crossing_id] = amount_cents


class SyntheticPaymentProvider(PassengerPaymentConfirmation, PassengerPayment):
    def __init__(self, fail_tokens: Optional[set] = None) -> None:
        self.fail_tokens = fail_tokens or set()
        self.charges: Dict[str, dict] = {}
        self.refunds: List[str] = []
        self._n = 0

    def charge(self, method_token: str, amount_cents: int, reference: str) -> str:
        if method_token in self.fail_tokens:
            raise RuntimeError("simulated passenger charge failed")
        self._n += 1
        charge_id = f"PCH-{self._n:04d}"
        self.charges[charge_id] = {
            "token": method_token,
            "amount_cents": amount_cents,
            "reference": reference,
        }
        return charge_id

    def refund(self, charge_id: str) -> str:
        if charge_id not in self.charges:
            raise KeyError(charge_id)
        self.refunds.append(charge_id)
        return f"REF-{charge_id}"

    def confirmation(self, charge_id: str) -> Optional[PaymentConfirmation]:
        row = self.charges.get(charge_id)
        if row is None:
            return None
        return PaymentConfirmation(
            charge_id=charge_id,
            reference=row["reference"],
            amount_cents=row["amount_cents"],
            method_token=row["token"],
            confirmed=True,
            simulated=True,
        )


class SyntheticEzPassProvider(EzPassCreditConfirmation, EzPassDirectory):
    def __init__(self, accounts: List[EzPassAccount], fail_accounts: Optional[set] = None) -> None:
        self.accounts = {account.vehicle_id: account for account in accounts}
        self.by_id = {account.account_id: account for account in accounts}
        self.fail_accounts = fail_accounts or set()
        self.credits: List[dict] = []

    def account_for_vehicle(self, vehicle_id: str) -> Optional[EzPassAccount]:
        return self.accounts.get(vehicle_id)

    def credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        if account_id in self.fail_accounts:
            raise RuntimeError("simulated E-ZPass credit failed")
        account = self.by_id[account_id]
        credit_id = f"EZC-{len(self.credits)+1:04d}"
        account.balance_cents += amount_cents
        self.credits.append({
            "id": credit_id,
            "account_id": account_id,
            "amount_cents": amount_cents,
            "reference": reference,
        })
        return credit_id

    def reverse_credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        account = self.by_id[account_id]
        account.balance_cents -= amount_cents
        rev = f"EZR-{len(self.credits)+1:04d}"
        self.credits.append({
            "id": rev,
            "account_id": account_id,
            "amount_cents": -amount_cents,
            "reference": reference,
        })
        return rev

    def confirmation(self, credit_id: str) -> Optional[CreditConfirmation]:
        for row in self.credits:
            if row["id"] == credit_id:
                return CreditConfirmation(
                    credit_id=credit_id,
                    account_id=row["account_id"],
                    reference=row["reference"],
                    amount_cents=row["amount_cents"],
                    confirmed=row["amount_cents"] > 0,
                    simulated=True,
                )
        return None
