"""Executable zero-balance timing demonstration. Simulation only."""

from datetime import datetime, timedelta, timezone

from tolldirect.core.timing import PaymentTimingModel, CreditTiming, PaymentStage


APPROACH = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
CROSSED = APPROACH + timedelta(minutes=4)
POSTED = CROSSED + timedelta(days=3)


def run() -> None:
    model = PaymentTimingModel()
    print("TollDirect timing demonstration — simulation only")
    print("E-ZPass real-time external credit: not verified")
    print("Driver funding used: no")
    print()
    for timing in (CreditTiming.BEFORE_CROSSING, CreditTiming.AT_CROSSING, CreditTiming.AFTER_OFFICIAL_POST):
        result = model.run("GX-DEMO", 350, 0, APPROACH, CROSSED, POSTED, timing)
        print(f"== {timing.value} ==")
        for event in result.stages:
            print(f"{event.at.isoformat()}  {event.stage.value:24}  balance={event.ezpass_balance_cents}  {event.note}")
        exposure = result.exposure
        print(f"exposure={exposure.exposed}  {exposure.reason}")
        print(f"charge={result.passenger_charge_id} credit={result.ezpass_credit_id} realtime_verified={result.realtime_credit_verified}")
        print()
    after = model.run("GX-DEMO", 350, 0, APPROACH, CROSSED, POSTED, CreditTiming.AFTER_OFFICIAL_POST)
    authorized = after.stage_at(PaymentStage.AUTHORIZED)
    confirmed = after.stage_at(PaymentStage.CONFIRMED_EZPASS_CREDIT)
    assert authorized.ezpass_balance_cents == 0
    assert confirmed.ezpass_balance_cents == 350
    assert after.exposure.exposed is True


if __name__ == "__main__":
    run()
