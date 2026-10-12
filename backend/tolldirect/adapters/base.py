"""Integration adapter contracts. Official Uber and E-ZPass adapters can replace these later."""

from abc import ABC, abstractmethod
from typing import Optional, List
from ..models import Trip, Crossing, EzPassAccount


class TripSource(ABC):
    @abstractmethod
    def active_trips(self) -> List[Trip]:
        raise NotImplementedError

    @abstractmethod
    def find_trip_for_vehicle(self, vehicle_id: str, when) -> Optional[Trip]:
        raise NotImplementedError


class CrossingSource(ABC):
    @abstractmethod
    def poll(self) -> List[Crossing]:
        raise NotImplementedError

    @abstractmethod
    def official_amount(self, crossing_id: str) -> Optional[int]:
        raise NotImplementedError


class EzPassDirectory(ABC):
    @abstractmethod
    def account_for_vehicle(self, vehicle_id: str) -> Optional[EzPassAccount]:
        raise NotImplementedError

    @abstractmethod
    def credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError

    def reverse_credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError


class PassengerPayment(ABC):
    """Charges only the passenger method already authorized for the trip. Never the driver."""

    @abstractmethod
    def charge(self, method_token: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def refund(self, charge_id: str) -> str:
        raise NotImplementedError
