"""Provider-independent contracts.

Official Uber, Lyft, and E-ZPass adapters can implement these later.
The core rules do not depend on a specific provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ..models import Trip, Crossing, EzPassAccount


@dataclass
class TripEvent:
    event_id: str
    trip: Trip
    kind: str  # started or ended
    at: datetime


@dataclass
class CrossingRecord:
    event_id: str
    crossing: Crossing


@dataclass
class PaymentConfirmation:
    charge_id: str
    reference: str
    amount_cents: int
    method_token: str
    confirmed: bool
    simulated: bool = True


@dataclass
class CreditConfirmation:
    credit_id: str
    account_id: str
    reference: str
    amount_cents: int
    confirmed: bool
    simulated: bool = True


class TripEventSource(ABC):
    """Active passenger trips. No driver payment method is exposed."""

    @abstractmethod
    def events(self) -> List[TripEvent]:
        raise NotImplementedError

    @abstractmethod
    def find_trip_for_vehicle(self, vehicle_id: str, when: datetime) -> Optional[Trip]:
        raise NotImplementedError


class TollCrossingSource(ABC):
    """Gantry records and later official posted amounts."""

    @abstractmethod
    def records(self) -> List[CrossingRecord]:
        raise NotImplementedError

    @abstractmethod
    def official_amount(self, crossing_id: str) -> Optional[int]:
        raise NotImplementedError


class PassengerPaymentConfirmation(ABC):
    """Confirms a charge against the passenger method already authorized for the trip."""

    @abstractmethod
    def charge(self, method_token: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def refund(self, charge_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def confirmation(self, charge_id: str) -> Optional[PaymentConfirmation]:
        raise NotImplementedError


class EzPassCreditConfirmation(ABC):
    """Confirms a credit to the vehicle E-ZPass account. No bank destination."""

    @abstractmethod
    def account_for_vehicle(self, vehicle_id: str) -> Optional[EzPassAccount]:
        raise NotImplementedError

    @abstractmethod
    def credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def reverse_credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def confirmation(self, credit_id: str) -> Optional[CreditConfirmation]:
        raise NotImplementedError
