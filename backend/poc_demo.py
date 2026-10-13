"""Complete TollDirect proof of concept. Synthetic data only.

Run from the backend directory:

    python poc_demo.py

On Windows the same command works in Command Prompt or PowerShell.
No network calls, no credentials, and no real payments.
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tolldirect.engine import Engine
from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount, SettlementStatus
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments
from tolldirect.core.timing import PaymentTimingModel, CreditTiming, PaymentStage


NOW = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)


def build_world(path: str):
    trips = [
        Trip("T-UBER-100", "uber", "V-441", "pm_passenger_ok", NOW - timedelta(minutes=22)),
        Trip("T-LYFT-200", "lyft", "V-220", "pm_passenger_fail", NOW - timedelta(minutes=12), NOW + timedelta(minutes=20)),
    ]
    accounts = [
        EzPassAccount("EZ-MA-441", "V-441", "4821", 2500),
        EzPassAccount("EZ-MA-220", "V-220", "1104", 0),
    ]
    crossings = [
        Crossing("GX-TOBIN-2201", "V-441", "MA-441", "TAG-77", "Tobin Bridge", NOW - timedelta(minutes=4)),
        Crossing("GX-SUMNER-2194", "V-220", "MA-220", "TAG-12", "Sumner Tunnel", NOW - timedelta(minutes=1), 265),
        Crossing("GX-TOBIN-2201", "V-441", "MA-441", "TAG-77", "Tobin Bridge", NOW),
    ]
    ez = SyntheticEzPass(accounts, crossings, {"GX-TOBIN-2201": 350})
    pay = SyntheticPayments({"pm_passenger_fail"})
    engine = Engine(SyntheticTnc(trips), ez, ez, pay, Store(path))
    return engine, ez, pay


def line(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def run(store_path: str | None = None) -> dict:
    path = store_path or str(Path(tempfile.gettempdir()) / "tolldirect-poc.db")
    engine, ez, pay = build_world(path)
    ingested = engine.ingest()
    applied = engine.apply_official_posts()
    report = engine.reconcile()

    line("1. Synthetic passenger trip and automatic match")
    print("Trip T-UBER-100  Uber  vehicle V-441  passenger method pm_passenger_ok")
    print("Crossing GX-TOBIN-2201  Tobin Bridge  plate MA-441  tag TAG-77")
    matched = engine.get("GX-TOBIN-2201")
    print(f"Matched trip {matched.trip_id} to E-ZPass {matched.ezpass_account_id} ending {ez.by_id['EZ-MA-441'].last4}")
    print(f"Status after official post: {matched.status.value}  amount {matched.amount_cents} cents")
    print("Driver bank account: not present")
    print("Driver-funded recharge: not used")

    line("2. Timestamped payment stages for the matched toll")
    model = PaymentTimingModel()
    approach = NOW - timedelta(minutes=6)
    crossed = NOW - timedelta(minutes=4)
    posted = crossed + timedelta(days=3)
    early = model.run("GX-TOBIN-2201", 350, 0, approach, crossed, posted, CreditTiming.BEFORE_CROSSING)
    late = model.run("GX-TOBIN-2201", 350, 0, approach, crossed, posted, CreditTiming.AFTER_OFFICIAL_POST)
    print("Stages are simulated. Authorization does not increase the E-ZPass balance.")
    for event in early.stages:
        print(f"{event.at.isoformat()}  {event.stage.value:24}  balance={event.ezpass_balance_cents:>4}  {event.note}")

    line("3. Zero-balance scenario: proposed credit before assessment")
    print(f"Approach balance: {early.balance_at_approach_cents} cents")
    print(f"Confirmed credit at: {early.stage_at(PaymentStage.CONFIRMED_EZPASS_CREDIT).at.isoformat()}")
    print(f"Exposure: {early.exposure.exposed}")
    print(early.exposure.reason)
    print("Real-time external E-ZPass credit verified: no")

    line("4. Zero-balance scenario: credit arrives after official post")
    print(f"Official post at: {posted.isoformat()}")
    print(f"Confirmed credit at: {late.stage_at(PaymentStage.CONFIRMED_EZPASS_CREDIT).at.isoformat()}")
    print(f"Exposure: {late.exposure.exposed}  gap={late.exposure.gap}")
    print(late.exposure.reason)
    print("Driver funding used to cover the gap: no")

    line("5. Duplicate prevention and reconciliation")
    print(f"Ingested events: {ingested}")
    print(f"Official posts applied: {applied}")
    print(f"Duplicates blocked: {engine.duplicates_blocked}")
    print(f"Passenger charges: {len(pay.charges)}")
    print(f"Reconciliation: {report}")
    failed = engine.get("GX-SUMNER-2194")
    print(f"Failed passenger charge {failed.crossing_id}: {failed.status.value} / {failed.failure_reason}")
    print("No driver or Uber/Lyft funds were used for the failed charge.")

    line("6. Transaction ledger")
    print(f"{'entry':<12} {'time':<28} {'kind':<24} {'crossing':<18} {'amount':>7}  detail")
    for entry in engine.store.ledger():
        print(
            f"{entry.entry_id:<12} {entry.at.isoformat():<28} {entry.kind:<24} "
            f"{entry.crossing_id:<18} {entry.amount_cents:>7}  {entry.detail}"
        )

    line("Simulation boundary")
    print("SIMULATION ONLY. No Uber, Lyft, E-ZPass, bank, or card system was contacted.")
    print(f"Durable store: {path}")

    return {
        "matched_status": matched.status,
        "matched_trip": matched.trip_id,
        "matched_account": matched.ezpass_account_id,
        "amount_cents": matched.amount_cents,
        "duplicates_blocked": engine.duplicates_blocked,
        "charges": len(pay.charges),
        "balanced": report["balanced"],
        "failed_status": failed.status,
        "early_exposed": early.exposure.exposed,
        "late_exposed": late.exposure.exposed,
        "ledger": engine.store.ledger(),
        "store_path": path,
    }


def main() -> None:
    result = run()
    if result["matched_status"] is not SettlementStatus.RECONCILED:
        raise SystemExit("expected the matched toll to reconcile")
    if result["late_exposed"] is not True:
        raise SystemExit("expected late credit to remain exposed")
    if result["balanced"] is not True:
        raise SystemExit("expected reconciliation to balance")


if __name__ == "__main__":
    main()
