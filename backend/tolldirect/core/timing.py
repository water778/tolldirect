"""Payment timing model. Authorization is not an E-ZPass credit."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional


class PaymentStage(str, Enum):
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    CONFIRMED_EZPASS_CREDIT = "confirmed_ezpass_credit"


class CreditTiming(str, Enum):
    BEFORE_CROSSING = "before_crossing"
    AT_CROSSING = "at_crossing"
    AFTER_OFFICIAL_POST = "after_official_post"


@dataclass
class StageEvent:
    at: datetime
    stage: PaymentStage
    amount_cents: int
    ezpass_balance_cents: int
    note: str


@dataclass
class Exposure:
    exposed: bool
    reason: str
    post_at: Optional[datetime] = None
    credit_at: Optional[datetime] = None
    gap: Optional[timedelta] = None
    driver_funding_used: bool = False


@dataclass
class TimingResult:
    crossing_id: str
    timing: CreditTiming
    balance_at_approach_cents: int
    stages: List[StageEvent] = field(default_factory=list)
    exposure: Optional[Exposure] = None
    passenger_charge_id: Optional[str] = None
    ezpass_credit_id: Optional[str] = None
    ezpass_balance_after_cents: int = 0
    simulation_only: bool = True
    realtime_credit_verified: bool = False
    driver_funding_used: bool = False
    credit_deferred: bool = False

    def stage_at(self, stage: PaymentStage) -> Optional[StageEvent]:
        for event in self.stages:
            if event.stage is stage:
                return event
        return None


class PaymentTimingModel:
    """Models when passenger funds become an E-ZPass balance.

    An authorized or captured passenger payment does not change the
    E-ZPass balance. Only a confirmed credit does.
    Real-time external credit is not treated as an existing E-ZPass capability.
    """

    def run(
        self,
        crossing_id: str,
        amount_cents: int,
        balance_at_approach_cents: int,
        approach_at: datetime,
        crossed_at: datetime,
        official_post_at: datetime,
        timing: CreditTiming,
        credit_delay_after_post: timedelta = timedelta(days=2),
    ) -> TimingResult:
        if amount_cents <= 0:
            raise ValueError("amount must be a recorded positive toll")
        result = TimingResult(
            crossing_id=crossing_id,
            timing=timing,
            balance_at_approach_cents=balance_at_approach_cents,
            ezpass_balance_after_cents=balance_at_approach_cents,
        )
        balance = balance_at_approach_cents
        result.stages.append(StageEvent(
            approach_at, PaymentStage.AUTHORIZED, amount_cents, balance,
            "passenger method authorized for the trip; E-ZPass balance unchanged",
        ))
        capture_at = approach_at + timedelta(seconds=5)
        result.stages.append(StageEvent(
            capture_at, PaymentStage.CAPTURED, amount_cents, balance,
            "passenger charge captured; E-ZPass balance unchanged",
        ))
        settle_at = capture_at + timedelta(minutes=30)
        result.stages.append(StageEvent(
            settle_at, PaymentStage.SETTLED, amount_cents, balance,
            "passenger funds settled to the payment path; E-ZPass balance unchanged",
        ))
        desired = self._credit_time(timing, crossed_at, official_post_at, credit_delay_after_post)
        # A confirmed credit cannot precede a captured passenger payment.
        credit_at = max(desired, capture_at)
        result.credit_deferred = credit_at > desired
        balance += amount_cents
        result.ezpass_balance_after_cents = balance
        result.stages.append(StageEvent(
            credit_at, PaymentStage.CONFIRMED_EZPASS_CREDIT, amount_cents, balance,
            "confirmed credit to the vehicle E-ZPass account; this is the first balance increase",
        ))
        result.passenger_charge_id = f"PCH-{crossing_id}"
        result.ezpass_credit_id = f"EZC-{crossing_id}"
        result.exposure = self.assess_exposure(
            balance_at_approach_cents, amount_cents, crossed_at, official_post_at, credit_at,
        )
        return result

    def _credit_time(
        self,
        timing: CreditTiming,
        crossed_at: datetime,
        official_post_at: datetime,
        delay: timedelta,
    ) -> datetime:
        if timing is CreditTiming.BEFORE_CROSSING:
            return crossed_at - timedelta(minutes=2)
        if timing is CreditTiming.AT_CROSSING:
            return crossed_at
        return official_post_at + delay

    def assess_exposure(
        self,
        balance_at_approach_cents: int,
        amount_cents: int,
        crossed_at: datetime,
        official_post_at: datetime,
        credit_at: datetime,
    ) -> Exposure:
        """A toll can be assessed against a zero balance if credit lands after travel."""
        if balance_at_approach_cents >= amount_cents:
            return Exposure(False, "recorded balance covered the toll at approach", crossed_at, credit_at)
        if credit_at <= crossed_at:
            return Exposure(
                False,
                "proposed pre-crossing or at-crossing credit would cover the toll; this capability is not verified for E-ZPass",
                official_post_at,
                credit_at,
            )
        return Exposure(
            True,
            "official post can occur before the E-ZPass credit; zero-balance assessment risk remains",
            official_post_at,
            credit_at,
            credit_at - official_post_at,
        )
