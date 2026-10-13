"""Contract checks a future real adapter must pass. Synthetic adapters are the only implementations."""

from typing import Optional

from .contracts import (
    TripEventSource,
    TollCrossingSource,
    PassengerPaymentConfirmation,
    EzPassCreditConfirmation,
)


class AdapterContractError(AssertionError):
    pass


def require_trip_source(adapter: TripEventSource) -> None:
    if not isinstance(adapter, TripEventSource):
        raise AdapterContractError("adapter must implement TripEventSource")
    if not hasattr(adapter, "events") or not hasattr(adapter, "find_trip_for_vehicle"):
        raise AdapterContractError("trip source missing event methods")


def require_crossing_source(adapter: TollCrossingSource) -> None:
    if not isinstance(adapter, TollCrossingSource):
        raise AdapterContractError("adapter must implement TollCrossingSource")


def require_payment_confirmation(adapter: PassengerPaymentConfirmation) -> None:
    if not isinstance(adapter, PassengerPaymentConfirmation):
        raise AdapterContractError("adapter must implement PassengerPaymentConfirmation")
    for name in ("charge", "refund", "confirmation"):
        if not hasattr(adapter, name):
            raise AdapterContractError(f"payment adapter missing {name}")


def require_ezpass_confirmation(adapter: EzPassCreditConfirmation) -> None:
    if not isinstance(adapter, EzPassCreditConfirmation):
        raise AdapterContractError("adapter must implement EzPassCreditConfirmation")
    for name in ("account_for_vehicle", "credit", "reverse_credit", "confirmation"):
        if not hasattr(adapter, name):
            raise AdapterContractError(f"E-ZPass adapter missing {name}")
    if hasattr(adapter, "bank_account") or hasattr(adapter, "driver_recharge"):
        raise AdapterContractError("driver bank or recharge is not a permitted destination")


def require_credit_not_implied_by_authorization(payment: PassengerPaymentConfirmation, ezpass: EzPassCreditConfirmation) -> None:
    """An authorized passenger method must not be treated as an E-ZPass balance increase."""
    if hasattr(payment, "implies_ezpass_credit") and payment.implies_ezpass_credit():
        raise AdapterContractError("authorization must not imply an E-ZPass credit")
    if hasattr(ezpass, "realtime_external_credit_supported") and ezpass.realtime_external_credit_supported():
        raise AdapterContractError("real-time external E-ZPass credit is not verified")


class UnimplementedRealAdapter:
    """Placeholder for a future authorized provider. It intentionally fails the contracts."""

    name = "unimplemented-real-adapter"
    realtime_external_credit_verified = False

    def events(self):
        raise NotImplementedError("no authorized trip feed")

    def find_trip_for_vehicle(self, vehicle_id: str, when):
        raise NotImplementedError("no authorized trip feed")

    def records(self):
        raise NotImplementedError("no authorized crossing feed")

    def official_amount(self, crossing_id: str) -> Optional[int]:
        raise NotImplementedError("no authorized toll post feed")

    def charge(self, method_token: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError("no authorized passenger toll-portion charge")

    def refund(self, charge_id: str) -> str:
        raise NotImplementedError("no authorized refund path")

    def confirmation(self, charge_id: str):
        raise NotImplementedError("no payment confirmation")

    def account_for_vehicle(self, vehicle_id: str):
        raise NotImplementedError("no authorized E-ZPass account lookup")

    def credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError("no verified E-ZPass external credit")

    def reverse_credit(self, account_id: str, amount_cents: int, reference: str) -> str:
        raise NotImplementedError("no verified E-ZPass credit reversal")

    def realtime_external_credit_supported(self) -> bool:
        return False
