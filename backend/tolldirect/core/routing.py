"""Payment routing. Destination is always the vehicle E-ZPass account."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DestinationKind(str, Enum):
    EZPASS_ACCOUNT = "ezpass_account"


class RouteMode(str, Enum):
    SIMULATED = "simulated"
    CONFIRMED_CREDIT = "confirmed_ezpass_credit"


class RouteStatus(str, Enum):
    PLANNED = "planned"
    REJECTED = "rejected"
    SIMULATED_CHARGED = "simulated_charged"
    SIMULATED_CREDITED = "simulated_credited"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class EzPassDestination:
    """Only permitted destination. No bank account fields exist."""

    account_id: str
    vehicle_id: str
    last4: str
    kind: DestinationKind = DestinationKind.EZPASS_ACCOUNT


@dataclass
class RoutePlan:
    crossing_id: str
    amount_cents: int
    passenger_method_token: str
    destination: EzPassDestination
    mode: RouteMode = RouteMode.SIMULATED
    status: RouteStatus = RouteStatus.PLANNED
    passenger_charge_id: Optional[str] = None
    ezpass_credit_id: Optional[str] = None
    driver_funding_used: bool = False
    reason: str = ""

    def mark_simulated_charge(self, charge_id: str) -> None:
        self.passenger_charge_id = charge_id
        self.status = RouteStatus.SIMULATED_CHARGED
        self.mode = RouteMode.SIMULATED

    def mark_simulated_credit(self, credit_id: str) -> None:
        if not self.passenger_charge_id:
            raise ValueError("cannot credit before a passenger charge is recorded")
        self.ezpass_credit_id = credit_id
        self.status = RouteStatus.SIMULATED_CREDITED
        self.mode = RouteMode.SIMULATED

    def confirm(self) -> None:
        """Confirmed only when both a passenger charge and an E-ZPass credit id exist."""
        if not self.passenger_charge_id or not self.ezpass_credit_id:
            raise ValueError("confirmed status requires a charge id and an E-ZPass credit id")
        self.status = RouteStatus.CONFIRMED
        self.mode = RouteMode.CONFIRMED_CREDIT


class PaymentRouter:
    """Routes a passenger-funded toll to the vehicle E-ZPass account.

    The driver's bank is not a destination. A simulated event is never
    treated as a confirmed E-ZPass credit until a credit identifier is set.
    """

    def plan(
        self,
        crossing_id: str,
        amount_cents: int,
        passenger_method_token: str,
        destination: EzPassDestination,
    ) -> RoutePlan:
        self._reject_non_ezpass(destination)
        if amount_cents <= 0:
            return RoutePlan(
                crossing_id=crossing_id,
                amount_cents=amount_cents,
                passenger_method_token=passenger_method_token,
                destination=destination,
                status=RouteStatus.REJECTED,
                reason="amount must be a verified positive recorded toll",
            )
        if not passenger_method_token:
            return RoutePlan(
                crossing_id=crossing_id,
                amount_cents=amount_cents,
                passenger_method_token=passenger_method_token,
                destination=destination,
                status=RouteStatus.REJECTED,
                reason="missing passenger trip payment method",
            )
        return RoutePlan(
            crossing_id=crossing_id,
            amount_cents=amount_cents,
            passenger_method_token=passenger_method_token,
            destination=destination,
            reason="passenger funds planned to vehicle E-ZPass; simulation only",
        )

    def _reject_non_ezpass(self, destination: EzPassDestination) -> None:
        if not isinstance(destination, EzPassDestination):
            raise TypeError("destination must be an EzPassDestination")
        if destination.kind is not DestinationKind.EZPASS_ACCOUNT:
            raise ValueError("only an E-ZPass account destination is permitted")
        if not destination.account_id:
            raise ValueError("E-ZPass account id required")
