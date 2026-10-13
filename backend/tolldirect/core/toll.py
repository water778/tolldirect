"""Toll amount verification. Only recorded official amounts are accepted."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TollStatus(str, Enum):
    PENDING_OFFICIAL = "pending_official"
    VERIFIED = "verified"
    INVALID = "invalid"
    ADJUSTMENT_DELTA = "adjustment_delta"


@dataclass
class TollVerification:
    status: TollStatus
    amount_cents: Optional[int] = None
    delta_cents: Optional[int] = None
    invented: bool = False
    reason: str = ""


class TollVerifier:
    """Accepts only amounts already recorded by an official toll post.

    This module never estimates, invents, or substitutes a photo, GPS
    reading, or default fare for a missing official amount.
    """

    def verify(self, recorded_cents: Optional[int]) -> TollVerification:
        if recorded_cents is None:
            return TollVerification(
                TollStatus.PENDING_OFFICIAL,
                reason="official post not available; amount not invented",
            )
        if recorded_cents <= 0:
            return TollVerification(
                TollStatus.INVALID,
                reason="recorded amount must be a positive integer cents value",
            )
        return TollVerification(
            TollStatus.VERIFIED,
            amount_cents=recorded_cents,
            reason="accepted recorded official amount",
        )

    def commercial_delta(self, original_cents: int, new_official_cents: int) -> TollVerification:
        """A commercial-rate change is a delta on the same crossing, not a new toll."""
        if original_cents is None or new_official_cents is None:
            return TollVerification(TollStatus.INVALID, reason="both amounts required for adjustment")
        if new_official_cents <= original_cents:
            return TollVerification(
                TollStatus.INVALID,
                reason="non-positive commercial adjustment is not auto-applied",
            )
        delta = new_official_cents - original_cents
        return TollVerification(
            TollStatus.ADJUSTMENT_DELTA,
            amount_cents=new_official_cents,
            delta_cents=delta,
            reason="commercial-rate delta only; original charge is not repeated",
        )
