"""TollDirect models. Simulation only. No real money."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SettlementStatus(str, Enum):
    DETECTED = "detected"
    MATCHED = "matched"
    AWAITING_OFFICIAL_AMOUNT = "awaiting_official_amount"
    PASSENGER_CHARGE_PENDING = "passenger_charge_pending"
    PASSENGER_CHARGED = "passenger_charged"
    CREDITED_TO_EZPASS = "credited_to_ezpass"
    RECONCILED = "reconciled"
    FAILED_UNRESOLVED = "failed_unresolved"
    REFUNDED = "refunded"
    DUPLICATE_BLOCKED = "duplicate_blocked"


@dataclass
class Trip:
    trip_id: str
    tnc: str
    vehicle_id: str
    passenger_method_token: str
    started_at: datetime
    ended_at: Optional[datetime] = None

    def is_active_at(self, when: datetime) -> bool:
        if when < self.started_at:
            return False
        if self.ended_at is not None and when > self.ended_at:
            return False
        return True


@dataclass
class EzPassAccount:
    account_id: str
    vehicle_id: str
    last4: str
    balance_cents: int = 0


@dataclass
class Crossing:
    crossing_id: str
    vehicle_id: str
    plate: str
    transponder: str
    gantry: str
    crossed_at: datetime
    official_amount_cents: Optional[int] = None
    official_posted_at: Optional[datetime] = None


@dataclass
class LedgerEntry:
    entry_id: str
    at: datetime
    kind: str
    crossing_id: str
    detail: str
    amount_cents: int = 0
    status: str = ""


@dataclass
class Settlement:
    crossing_id: str
    vehicle_id: str = ""
    crossed_at: Optional[datetime] = None
    status: SettlementStatus = SettlementStatus.DETECTED
    trip_id: Optional[str] = None
    tnc: Optional[str] = None
    ezpass_account_id: Optional[str] = None
    amount_cents: Optional[int] = None
    passenger_charge_id: Optional[str] = None
    ezpass_credit_id: Optional[str] = None
    passenger_method_token: Optional[str] = None
    adjustment_cents: int = 0
    retry_count: int = 0
    failure_reason: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def touch(self) -> None:
        self.updated_at = utcnow()
