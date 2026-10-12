"""Seed the bundled read-only demonstration database. Synthetic data only."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tolldirect.engine import Engine
from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments

DB = Path(__file__).resolve().parent / "tolldirect" / "data" / "demo-readonly.db"


def main() -> None:
    DB.parent.mkdir(exist_ok=True)
    if DB.exists():
        DB.unlink()
    now = datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc)
    trips = [
        Trip("T-100", "uber", "V-1", "pm_ok", now - timedelta(minutes=25)),
        Trip("T-200", "lyft", "V-2", "pm_fail", now - timedelta(minutes=12)),
        Trip("T-300", "uber", "V-3", "pm_ok", now - timedelta(minutes=40), now - timedelta(minutes=5)),
    ]
    accounts = [
        EzPassAccount("EZ-1", "V-1", "4821", 2500),
        EzPassAccount("EZ-2", "V-2", "1104", 800),
        EzPassAccount("EZ-3", "V-3", "7730", 1200),
    ]
    crossings = [
        Crossing("GX-2201", "V-1", "MA-441", "TAG-77", "Tobin Bridge", now - timedelta(minutes=6)),
        Crossing("GX-2194", "V-2", "MA-220", "TAG-12", "Sumner Tunnel", now - timedelta(minutes=2), 265),
        Crossing("GX-2180", "V-3", "MA-018", "TAG-03", "Callahan Tunnel", now - timedelta(minutes=1), 265),
        Crossing("GX-2201", "V-1", "MA-441", "TAG-77", "Tobin Bridge", now),
    ]
    ez = SyntheticEzPass(accounts, crossings, {"GX-2201": 350})
    engine = Engine(SyntheticTnc(trips), ez, ez, SyntheticPayments({"pm_fail"}), Store(str(DB)))
    engine.ingest()
    engine.apply_official_posts()
    engine.apply_commercial_adjustment("GX-2201", 500)
    print(DB)


if __name__ == "__main__":
    main()
