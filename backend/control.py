"""Internal TollDirect Control Center. Simulation only."""

import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tolldirect.engine import Engine
from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments

DB = Path("/tmp/tolldirect-control.db")


def seed() -> Store:
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
    pay = SyntheticPayments({"pm_fail"})
    store = Store(str(DB))
    engine = Engine(SyntheticTnc(trips), ez, ez, pay, store)
    engine.ingest()
    engine.apply_official_posts()
    engine.apply_commercial_adjustment("GX-2201", 500)
    store.demo_accounts = accounts
    return store


def money(cents) -> str:
    return "-" if cents is None else f"${cents/100:.2f}"


def page(store: Store) -> str:
    rows = []
    for s in store.all_settlements():
        rows.append(
            f"<tr><td>{s.crossing_id}</td><td>{s.trip_id or '-'}</td><td>{s.tnc or '-'}</td>"
            f"<td>{s.ezpass_account_id or '-'}</td><td>{money(s.amount_cents)}</td>"
            f"<td>{s.passenger_charge_id or '-'}</td><td>{s.ezpass_credit_id or '-'}</td>"
            f"<td class='{s.status.value}'>{s.status.value}</td><td>{s.failure_reason or ''}</td></tr>"
        )
    ledger = "".join(
        f"<tr><td>{e.entry_id}</td><td>{e.kind}</td><td>{e.crossing_id}</td><td>{e.detail}</td><td>{money(e.amount_cents)}</td></tr>"
        for e in store.ledger()
    )
    charged = sum((s.amount_cents or 0) for s in store.all_settlements() if s.passenger_charge_id and s.status.value != "refunded")
    credited = sum((s.amount_cents or 0) for s in store.all_settlements() if s.ezpass_credit_id and s.status.value != "refunded")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>TollDirect Control Center</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#f6f7f9;color:#172033}}
h1{{margin:0}} .sub{{color:#5b677a}}
table{{width:100%;border-collapse:collapse;background:#fff;margin:16px 0}}
th,td{{border-bottom:1px solid #e6e8ee;padding:8px;text-align:left;font-size:14px}}
.reconciled{{color:#0b7a3b}} .failed_unresolved{{color:#b42318}} .refunded{{color:#8a5a00}}
.banner{{background:#fff4d6;border:1px solid #efd48a;padding:10px;border-radius:8px}}
.cards{{display:flex;gap:12px}} .card{{background:#fff;padding:12px 16px;border-radius:8px}}
</style></head><body>
<p class="banner">SIMULATION ONLY. Synthetic data. No Uber, Lyft, E-ZPass, bank, or real payment connection.</p>
<h1>TollDirect Control Center</h1>
<p class="sub">Passenger payment → TollDirect processing → vehicle-linked E-ZPass account</p>
<div class="cards">
<div class="card"><b>Charged</b><br>{money(charged)}</div>
<div class="card"><b>Credited</b><br>{money(credited)}</div>
<div class="card"><b>Balanced</b><br>{"yes" if charged==credited else "no"}</div>
</div>
<h2>Transactions</h2>
<table><tr><th>Crossing</th><th>Trip</th><th>TNC</th><th>E-ZPass</th><th>Amount</th><th>Passenger charge</th><th>E-ZPass credit</th><th>Status</th><th>Note</th></tr>
{''.join(rows)}</table>
<h2>Audit ledger</h2>
<table><tr><th>ID</th><th>Kind</th><th>Crossing</th><th>Detail</th><th>Amount</th></tr>{ledger}</table>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    store = None

    def do_GET(self):
        body = page(self.store).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main() -> None:
    store = seed()
    Handler.store = store
    server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    print("TollDirect Control Center: http://127.0.0.1:8787")
    print("SIMULATION ONLY")
    server.serve_forever()


if __name__ == "__main__":
    main()
