"""Synthetic TNC, E-ZPass, and payment adapters. No external calls."""

from typing import Dict, List, Optional
from datetime import datetime
from ..models import Trip, Crossing, EzPassAccount
from .base import TripSource, CrossingSource, EzPassDirectory, PassengerPayment


class SyntheticTnc(TripSource):
    def __init__(self, trips: List[Trip]) -> None:
        self.trips = list(trips)

    def active_trips(self) -> List[Trip]:
        return [t for t in self.trips if t.ended_at is None]

    def find_trip_for_vehicle(self, vehicle_id: str, when: datetime) -> Optional[Trip]:
        matches = [t for t in self.trips if t.vehicle_id == vehicle_id and t.is_active_at(when)]
        if len(matches) != 1:
            return None
        return matches[0]


class SyntheticEzPass(CrossingSource, EzPassDirectory):
    def __init__(self, accounts: List[EzPassAccount], crossings: List[Crossing], delayed: Dict[str, int], fail_accounts: Optional[set] = None) -> None:
        self.accounts = {a.vehicle_id: a for a in accounts}
        self.by_id = {a.account_id: a for a in accounts}
        self._queue = list(crossings)
        self.delayed = dict(delayed)
        self.fail_accounts = fail_accounts or set()
        self.credits: List[dict] = []
        self._seen = set()

    def poll(self) -> List[Crossing]:
        batch, self._queue = self._queue, []
        return batch

    def official_amount(self, crossing_id: str) -> Optional[int]:
        return self.delayed.get(crossing_id)

    def account_for_vehicle(self, vehicle_id: str) -> Optional[EzPassAccount]:
        return self.accounts.get(vehicle_id)

    def credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        if account_id in self.fail_accounts:
            raise RuntimeError("simulated E-ZPass credit failed")
        account = self.by_id[account_id]
        credit_id = f"EZC-{len(self.credits)+1:04d}"
        account.balance_cents += amount_cents
        self.credits.append({"id": credit_id, "account_id": account_id, "amount_cents": amount_cents, "reference": reference})
        return credit_id

    def reverse_credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        account = self.by_id[account_id]
        account.balance_cents -= amount_cents
        rev = f"EZR-{len(self.credits)+1:04d}"
        self.credits.append({"id": rev, "account_id": account_id, "amount_cents": -amount_cents, "reference": reference})
        return rev


class SyntheticPayments(PassengerPayment):
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
        self.charges[charge_id] = {"token": method_token, "amount_cents": amount_cents, "reference": reference}
        return charge_id

    def refund(self, charge_id: str) -> str:
        if charge_id not in self.charges:
            raise KeyError(charge_id)
        self.refunds.append(charge_id)
        return f"REF-{charge_id}"
