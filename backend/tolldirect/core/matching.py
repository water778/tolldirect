"""Trip-to-toll matching. One crossing must match exactly one active passenger trip."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ..models import Crossing, Trip


class MatchOutcome(str, Enum):
    MATCHED = "matched"
    NONE = "none"
    AMBIGUOUS = "ambiguous"


@dataclass
class MatchResult:
    outcome: MatchOutcome
    trip: Optional[Trip] = None
    candidates: List[Trip] = field(default_factory=list)
    reason: str = ""

    @property
    def matched(self) -> bool:
        return self.outcome is MatchOutcome.MATCHED and self.trip is not None


class TripTollMatcher:
    """Associates a gantry crossing with the vehicle's active passenger trip.

    Matching uses only recorded facts: vehicle identity and trip window.
    Zero or multiple active trips are not charged. No trip is invented.
    """

    def match(self, crossing: Crossing, trips: List[Trip]) -> MatchResult:
        if not crossing.vehicle_id or crossing.crossed_at is None:
            return MatchResult(MatchOutcome.NONE, reason="crossing missing vehicle or time")
        candidates = [
            trip for trip in trips
            if trip.vehicle_id == crossing.vehicle_id and trip.is_active_at(crossing.crossed_at)
        ]
        if len(candidates) == 1:
            trip = candidates[0]
            return MatchResult(
                MatchOutcome.MATCHED,
                trip=trip,
                candidates=candidates,
                reason=f"vehicle {crossing.vehicle_id} matched trip {trip.trip_id}",
            )
        if not candidates:
            return MatchResult(MatchOutcome.NONE, reason="no active passenger trip for vehicle")
        return MatchResult(
            MatchOutcome.AMBIGUOUS,
            candidates=candidates,
            reason="more than one active trip; no charge",
        )
