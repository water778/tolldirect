"""Read-only simulation dashboard. No payment controls."""

import base64
import json
from pathlib import Path
from .store import Store

DEMO_USER = "demo"
DEMO_PASSWORD = "tolldirect-sim"
DB_PATH = Path(__file__).resolve().parent / "data" / "demo-readonly.db"


def authorized(header: str) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode()
    except Exception:
        return False
    user, _, password = raw.partition(":")
    return user == DEMO_USER and password == DEMO_PASSWORD


def health() -> dict:
    return {"status": "ok", "mode": "simulation", "payments": "disabled", "external_contacts": "disabled"}


def load_store() -> Store:
    return Store(str(DB_PATH))


def dashboard_html(store: Store) -> str:
    rows = []
    for s in store.all_settlements():
        rows.append(
            "<tr>"
            f"<td>{s.crossing_id}</td><td>{s.trip_id or '-'}</td><td>{s.tnc or '-'}</td>"
            f"<td>{s.ezpass_account_id or '-'}</td><td>{s.amount_cents if s.amount_cents is not None else '-'}</td>"
            f"<td>{s.passenger_charge_id or '-'}</td><td>{s.ezpass_credit_id or '-'}</td>"
            f"<td>{s.status.value}</td><td>{s.failure_reason or ''}</td></tr>"
        )
    ledger = "".join(
        f"<tr><td>{e.entry_id}</td><td>{e.kind}</td><td>{e.crossing_id}</td><td>{e.detail}</td></tr>"
        for e in store.ledger()
    )
    charged = sum((s.amount_cents or 0) for s in store.all_settlements() if s.passenger_charge_id and s.status.value != "refunded")
    credited = sum((s.amount_cents or 0) for s in store.all_settlements() if s.ezpass_credit_id and s.status.value != "refunded")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TollDirect Control Center</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f4f6f8;color:#172033}}
header,main{{padding:16px}}
.banner{{background:#fff4d6;border:1px solid #efd48a;border-radius:8px;padding:10px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}}
.card,.wrap{{background:#fff;border-radius:8px;padding:12px}}
table{{width:100%;border-collapse:collapse}}
th,td{{border-bottom:1px solid #e6e8ee;padding:8px;text-align:left;font-size:14px}}
.wrap{{overflow-x:auto}}
@media (max-width:700px){{
  .cards{{grid-template-columns:1fr}}
  header,main{{padding:12px}}
  th,td{{font-size:13px}}
}}
</style></head><body>
<header><p class="banner">SIMULATION ONLY. Synthetic data. Read-only. No real payments and no external connections.</p>
<h1>TollDirect Control Center</h1></header>
<main>
<div class="cards"><div class="card"><b>Charged cents</b><br>{charged}</div><div class="card"><b>Credited cents</b><br>{credited}</div><div class="card"><b>Balanced</b><br>{"yes" if charged==credited else "no"}</div></div>
<h2>Transactions</h2>
<div class="wrap"><table><tr><th>Crossing</th><th>Trip</th><th>TNC</th><th>E-ZPass</th><th>Amount</th><th>Charge</th><th>Credit</th><th>Status</th><th>Note</th></tr>{''.join(rows)}</table></div>
<h2>Audit ledger</h2>
<div class="wrap"><table><tr><th>ID</th><th>Kind</th><th>Crossing</th><th>Detail</th></tr>{ledger}</table></div>
</main></body></html>"""


def handle(method: str, path: str, authorization: str):
    if method != "GET":
        return 405, "application/json", json.dumps({"error": "read-only"})
    if path == "/health":
        return 200, "application/json", json.dumps(health())
    if not authorized(authorization):
        return 401, "application/json", json.dumps({"error": "authentication required"})
    if path in {"/", "/dashboard"}:
        return 200, "text/html; charset=utf-8", dashboard_html(load_store())
    return 404, "application/json", json.dumps({"error": "not found"})
