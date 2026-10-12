"""Internal monitoring dashboard. Reads the ledger and settlements. No external data."""

from .engine import Engine
from .models import SettlementStatus


def render(engine: Engine) -> str:
    rows = []
    for s in engine.settlements.values():
        rows.append(
            f"{s.crossing_id:12} {s.status.value:28} trip={s.trip_id or '-':10} "
            f"ez={s.ezpass_account_id or '-':8} amt={s.amount_cents if s.amount_cents is not None else '-':>6} "
            f"charge={s.passenger_charge_id or '-'} credit={s.ezpass_credit_id or '-'}"
        )
    counts = {st.value: 0 for st in SettlementStatus}
    for s in engine.settlements.values():
        counts[s.status.value] = counts.get(s.status.value, 0) + 1
    summary = " ".join(f"{k}={v}" for k, v in counts.items() if v)
    body = "\n".join(rows) if rows else "(no crossings)"
    ledger = "\n".join(f"{e.entry_id} {e.kind:22} {e.crossing_id} {e.detail}" for e in engine.ledger.all())
    return f"TollDirect monitor — simulation\n{summary}\n\n{body}\n\nLedger\n{ledger}\n"
