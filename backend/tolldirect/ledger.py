"""Append-only audit ledger. Simulation only."""

from typing import List
from .models import LedgerEntry, utcnow


class Ledger:
    def __init__(self) -> None:
        self._entries: List[LedgerEntry] = []
        self._seq = 0

    def append(self, kind: str, crossing_id: str, detail: str, amount_cents: int = 0, status: str = "") -> LedgerEntry:
        self._seq += 1
        entry = LedgerEntry(
            entry_id=f"LED-{self._seq:06d}",
            at=utcnow(),
            kind=kind,
            crossing_id=crossing_id,
            detail=detail,
            amount_cents=amount_cents,
            status=status,
        )
        self._entries.append(entry)
        return entry

    def all(self) -> List[LedgerEntry]:
        return list(self._entries)

    def for_crossing(self, crossing_id: str) -> List[LedgerEntry]:
        return [e for e in self._entries if e.crossing_id == crossing_id]
