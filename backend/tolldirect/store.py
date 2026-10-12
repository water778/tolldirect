"""Durable SQLite store for settlements and the audit ledger."""

import sqlite3
from datetime import datetime
from typing import List, Optional
from .models import Settlement, SettlementStatus, LedgerEntry


def _dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class Store:
    def __init__(self, path: str) -> None:
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=DELETE")
        self.conn.execute("PRAGMA synchronous=FULL")
        self._init()

    def _commit(self) -> None:
        last = None
        for _ in range(3):
            try:
                self.conn.commit()
                return
            except sqlite3.OperationalError as exc:
                last = exc
        raise last

    def _init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settlements (
                crossing_id TEXT PRIMARY KEY,
                vehicle_id TEXT,
                crossed_at TEXT,
                status TEXT,
                trip_id TEXT,
                tnc TEXT,
                ezpass_account_id TEXT,
                amount_cents INTEGER,
                passenger_charge_id TEXT UNIQUE,
                ezpass_credit_id TEXT UNIQUE,
                passenger_method_token TEXT,
                adjustment_cents INTEGER,
                retry_count INTEGER,
                failure_reason TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS ledger (
                entry_id TEXT PRIMARY KEY,
                at TEXT,
                kind TEXT,
                crossing_id TEXT,
                detail TEXT,
                amount_cents INTEGER,
                status TEXT
            );
            CREATE TABLE IF NOT EXISTS idempotency (
                key TEXT PRIMARY KEY,
                result TEXT
            );
            """
        )
        self._commit()

    def save(self, s: Settlement) -> None:
        self.conn.execute(
            """
            INSERT INTO settlements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(crossing_id) DO UPDATE SET
                vehicle_id=excluded.vehicle_id, crossed_at=excluded.crossed_at, status=excluded.status,
                trip_id=excluded.trip_id, tnc=excluded.tnc, ezpass_account_id=excluded.ezpass_account_id,
                amount_cents=excluded.amount_cents, passenger_charge_id=excluded.passenger_charge_id,
                ezpass_credit_id=excluded.ezpass_credit_id, passenger_method_token=excluded.passenger_method_token,
                adjustment_cents=excluded.adjustment_cents, retry_count=excluded.retry_count,
                failure_reason=excluded.failure_reason, updated_at=excluded.updated_at
            """,
            (
                s.crossing_id, s.vehicle_id, s.crossed_at.isoformat() if s.crossed_at else None, s.status.value,
                s.trip_id, s.tnc, s.ezpass_account_id, s.amount_cents, s.passenger_charge_id, s.ezpass_credit_id,
                s.passenger_method_token, s.adjustment_cents, s.retry_count, s.failure_reason,
                s.created_at.isoformat(), s.updated_at.isoformat(),
            ),
        )
        self._commit()

    def get(self, crossing_id: str) -> Optional[Settlement]:
        row = self.conn.execute("SELECT * FROM settlements WHERE crossing_id=?", (crossing_id,)).fetchone()
        return self._settlement(row) if row else None

    def all_settlements(self) -> List[Settlement]:
        return [self._settlement(r) for r in self.conn.execute("SELECT * FROM settlements ORDER BY created_at")]

    def append_ledger(self, entry: LedgerEntry) -> None:
        self.conn.execute(
            "INSERT INTO ledger VALUES (?,?,?,?,?,?,?)",
            (entry.entry_id, entry.at.isoformat(), entry.kind, entry.crossing_id, entry.detail, entry.amount_cents, entry.status),
        )
        self._commit()

    def ledger(self) -> List[LedgerEntry]:
        rows = self.conn.execute("SELECT * FROM ledger ORDER BY entry_id").fetchall()
        return [
            LedgerEntry(r["entry_id"], datetime.fromisoformat(r["at"]), r["kind"], r["crossing_id"], r["detail"], r["amount_cents"], r["status"])
            for r in rows
        ]

    def next_ledger_id(self) -> str:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM ledger").fetchone()
        return f"LED-{(row['n'] or 0)+1:06d}"

    def claim(self, key: str, result: str) -> bool:
        try:
            self.conn.execute("INSERT INTO idempotency VALUES (?,?)", (key, result))
            self._commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def claimed(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT result FROM idempotency WHERE key=?", (key,)).fetchone()
        return row["result"] if row else None

    def close(self) -> None:
        self.conn.close()

    def _settlement(self, r: sqlite3.Row) -> Settlement:
        return Settlement(
            crossing_id=r["crossing_id"],
            vehicle_id=r["vehicle_id"] or "",
            crossed_at=_dt(r["crossed_at"]),
            status=SettlementStatus(r["status"]),
            trip_id=r["trip_id"],
            tnc=r["tnc"],
            ezpass_account_id=r["ezpass_account_id"],
            amount_cents=r["amount_cents"],
            passenger_charge_id=r["passenger_charge_id"],
            ezpass_credit_id=r["ezpass_credit_id"],
            passenger_method_token=r["passenger_method_token"],
            adjustment_cents=r["adjustment_cents"] or 0,
            retry_count=r["retry_count"] or 0,
            failure_reason=r["failure_reason"],
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"]),
        )
