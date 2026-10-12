"""Run a durable synthetic demonstration."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tolldirect.engine import Engine
from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments


def main() -> None:
    now = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
    trips = [Trip("T-100", "uber", "V-1", "pm_ok", now - timedelta(minutes=20)), Trip("T-200", "lyft", "V-2", "pm_fail", now - timedelta(minutes=10))]
    accounts = [EzPassAccount("EZ-1", "V-1", "4821", 2500), EzPassAccount("EZ-2", "V-2", "1104", 800)]
    crossings = [
        Crossing("GX-2201", "V-1", "MA-441", "TAG-77", "Tobin Bridge", now - timedelta(minutes=4)),
        Crossing("GX-2194", "V-2", "MA-220", "TAG-12", "Sumner Tunnel", now - timedelta(minutes=1), official_amount_cents=265),
    ]
    ez = SyntheticEzPass(accounts, crossings, {"GX-2201": 350})
    store = Store("/tmp/tolldirect-demo.db")
    engine = Engine(SyntheticTnc(trips), ez, ez, SyntheticPayments({"pm_fail"}), store)
    print("Ingested", engine.ingest())
    print("Official posts applied", engine.apply_official_posts())
    print(engine.reconcile())
    for s in store.all_settlements():
        print(s.crossing_id, s.status.value, s.trip_id, s.ezpass_account_id, s.amount_cents, s.failure_reason or "")
    print("SIMULATION ONLY. Durable store:", store.path)


if __name__ == "__main__":
    main()
