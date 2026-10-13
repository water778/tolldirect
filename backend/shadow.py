"""Local shadow-test server. Simulation only. No credentials and no external calls.

Run from backend/:

    python shadow.py

Then open http://127.0.0.1:8765 on this computer.
For a private iPhone test on the same Wi-Fi:

    python shadow.py --lan
"""

import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tolldirect.engine import Engine
from tolldirect.store import Store
from tolldirect.models import Trip, Crossing, EzPassAccount
from tolldirect.adapters.synthetic import SyntheticTnc, SyntheticEzPass, SyntheticPayments
from tolldirect.core.timing import PaymentTimingModel, CreditTiming

HOST_LOCAL = "127.0.0.1"
PORT = 8765
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}${cents // 100}.{cents % 100:02d}"


def parse_when(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        return datetime.now(timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def reject_secrets(payload: dict) -> Optional[str]:
    blocked = {"password", "pin", "cvv", "ssn", "account_password", "username"}
    for key in payload:
        if key.lower() in blocked:
            return "Credentials are not accepted."
    text_fields = " ".join(
        str(payload.get(key) or "")
        for key in ("trip_ref", "vehicle_ref", "gantry", "ezpass_last4", "passenger_method")
    )
    if CARD_RE.search(text_fields):
        return "Enter only redacted references. Do not paste a full card or account number."
    return None


def shadow(payload: dict, store_path: Optional[str] = None) -> dict:
    error = reject_secrets(payload)
    if error:
        raise ValueError(error)
    trip_ref = str(payload.get("trip_ref") or "TRIP").strip()[:40]
    vehicle_ref = str(payload.get("vehicle_ref") or "VEHICLE").strip()[:40]
    last4 = re.sub(r"\D", "", str(payload.get("ezpass_last4") or ""))[-4:] or "0000"
    gantry = str(payload.get("gantry") or "Toll gantry").strip()[:60]
    tnc = str(payload.get("tnc") or "uber").strip().lower()
    if tnc not in {"uber", "lyft"}:
        tnc = "uber"
    try:
        uber_cents = int(payload.get("uber_toll_cents") or 0)
        ez_cents = int(payload.get("ezpass_toll_cents") or 0)
        balance = int(payload.get("ezpass_balance_cents") or 0)
    except (TypeError, ValueError):
        raise ValueError("Amounts must be whole cents.")
    if ez_cents <= 0 or ez_cents > 20000 or uber_cents < 0 or uber_cents > 20000:
        raise ValueError("Enter a recorded toll between $0.01 and $200.00.")
    when = parse_when(str(payload.get("crossed_at") or ""))
    path = store_path or tempfile.mktemp(suffix=".db")
    trip = Trip(f"T-{trip_ref}", tnc, vehicle_ref, "pm_redacted", when.replace(minute=max(0, when.minute - 10)))
    account = EzPassAccount(f"EZ-{last4}", vehicle_ref, last4, balance)
    crossing = Crossing(f"GX-{trip_ref}-{last4}", vehicle_ref, "REDACTED", "REDACTED", gantry, when, ez_cents)
    ez = SyntheticEzPass([account], [crossing], {})
    pay = SyntheticPayments()
    engine = Engine(SyntheticTnc([trip]), ez, ez, pay, Store(path))
    engine.ingest()
    engine.apply_official_posts()
    report = engine.reconcile()
    settlement = engine.get(crossing.crossing_id)
    delta = uber_cents - ez_cents
    if delta == 0:
        comparison = "The redacted trip toll and the recorded E-ZPass toll match."
    elif delta > 0:
        comparison = "The trip toll is higher than the recorded E-ZPass toll. Only the recorded E-ZPass amount is used."
    else:
        comparison = "The trip toll is lower than the recorded E-ZPass toll. Review the redacted amounts before any future settlement."
    model = PaymentTimingModel()
    timing = model.run(
        crossing.crossing_id,
        ez_cents,
        balance,
        when.replace(minute=max(0, when.minute - 4)),
        when,
        when,
        CreditTiming.AFTER_OFFICIAL_POST,
    )
    return {
        "simulation_only": True,
        "realtime_ezpass_credit_verified": False,
        "driver_funding_used": False,
        "destination_kind": "ezpass_account",
        "comparison": comparison,
        "uber_toll": money(uber_cents),
        "ezpass_toll": money(ez_cents),
        "difference": money(delta),
        "proposed_passenger_charge": money(ez_cents),
        "status": settlement.status.value,
        "trip_id": settlement.trip_id,
        "ezpass_account_id": settlement.ezpass_account_id,
        "ezpass_last4": last4,
        "passenger_charge_id": settlement.passenger_charge_id,
        "ezpass_credit_id": settlement.ezpass_credit_id,
        "amount_cents": settlement.amount_cents,
        "balanced": report["balanced"],
        "zero_balance_exposed": timing.exposure.exposed if balance < ez_cents else False,
        "exposure_reason": timing.exposure.reason,
        "ledger": [
            {
                "id": entry.entry_id,
                "at": entry.at.isoformat(),
                "kind": entry.kind,
                "detail": entry.detail,
                "amount": money(entry.amount_cents),
            }
            for entry in engine.store.ledger()
        ],
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TollDirect shadow test</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f4f6f8; color: #17202a; }
  header, main { width: min(100%, 430px); margin: 0 auto; padding: 16px; }
  header { padding-bottom: 0; }
  h1 { font-size: 22px; line-height: 1.2; margin: 8px 0 4px; }
  p { margin: 0 0 12px; line-height: 1.4; }
  .banner { background: #fff4e5; border: 1px solid #f0d7a8; border-radius: 12px; padding: 12px; font-size: 14px; }
  form, .card { background: white; border-radius: 16px; padding: 16px; margin: 12px 0; box-shadow: 0 1px 2px rgba(16,24,40,.06); }
  label { display: block; font-size: 13px; font-weight: 600; margin: 12px 0 6px; }
  input, select { width: 100%; max-width: 100%; font-size: 16px; padding: 12px; border: 1px solid #d0d7de; border-radius: 10px; background: white; }
  button { width: 100%; margin-top: 16px; border: 0; border-radius: 12px; background: #0b3a5b; color: white; font-size: 16px; font-weight: 700; padding: 14px; }
  .row { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eef2f5; font-size: 15px; }
  .row span:last-child { text-align: right; overflow-wrap: anywhere; }
  .ok { color: #067647; font-weight: 700; }
  .warn { color: #b54708; font-weight: 700; }
  .step { padding: 8px 0; font-size: 14px; overflow-wrap: anywhere; }
  .muted { color: #667085; font-size: 13px; }
</style>
</head>
<body>
<header>
  <div class="banner">Simulation only. Do not enter passwords, PINs, or full card or account numbers. No Uber or E-ZPass connection is made.</div>
  <h1>TollDirect shadow test</h1>
  <p class="muted">Compare a redacted trip toll with a recorded E-ZPass toll, then view the simulated passenger-to-E-ZPass flow.</p>
</header>
<main>
  <form id="form">
    <label>Rideshare</label>
    <select name="tnc"><option>uber</option><option>lyft</option></select>
    <label>Redacted trip reference</label>
    <input name="trip_ref" placeholder="Last 4 only" maxlength="40" required>
    <label>Redacted vehicle reference</label>
    <input name="vehicle_ref" placeholder="Vehicle code, not a plate" maxlength="40" required>
    <label>E-ZPass ending</label>
    <input name="ezpass_last4" inputmode="numeric" placeholder="4821" maxlength="4" required>
    <label>E-ZPass balance before crossing ($)</label>
    <input name="balance" inputmode="decimal" value="0.00" required>
    <label>Gantry or facility</label>
    <input name="gantry" placeholder="Tobin Bridge" maxlength="60" required>
    <label>Crossing time</label>
    <input name="crossed_at" type="datetime-local" required>
    <label>Trip toll charged to passenger ($)</label>
    <input name="uber_toll" inputmode="decimal" placeholder="3.50" required>
    <label>Recorded E-ZPass toll ($)</label>
    <input name="ezpass_toll" inputmode="decimal" placeholder="3.50" required>
    <button type="submit">Run simulated comparison</button>
  </form>
  <section id="result"></section>
</main>
<script>
const dollars = (value) => Math.round(Number(value) * 100);
document.getElementById("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  const body = {
    tnc: data.tnc,
    trip_ref: data.trip_ref,
    vehicle_ref: data.vehicle_ref,
    ezpass_last4: data.ezpass_last4,
    gantry: data.gantry,
    crossed_at: data.crossed_at,
    uber_toll_cents: dollars(data.uber_toll),
    ezpass_toll_cents: dollars(data.ezpass_toll),
    ezpass_balance_cents: dollars(data.balance)
  };
  const response = await fetch("/api/shadow", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const result = await response.json();
  const box = document.getElementById("result");
  if (!response.ok) {
    box.innerHTML = `<div class="card warn">${result.error}</div>`;
    return;
  }
  const rows = [
    ["Trip toll", result.uber_toll],
    ["E-ZPass toll", result.ezpass_toll],
    ["Difference", result.difference],
    ["Proposed passenger charge", result.proposed_passenger_charge],
    ["Destination", `E-ZPass ending ${result.ezpass_last4}`],
    ["Status", result.status],
    ["Driver funding", "Not used"]
  ].map(([name, value]) => `<div class="row"><span>${name}</span><span>${value}</span></div>`).join("");
  const ledger = result.ledger.map((entry) => `<div class="step"><strong>${entry.kind}</strong><br>${entry.amount} · ${entry.detail}</div>`).join("");
  box.innerHTML = `<div class="card"><p class="${result.difference === "$0.00" ? "ok" : "warn"}">${result.comparison}</p>${rows}<p class="muted">Real-time E-ZPass credit verified: no. Zero-balance exposure: ${result.zero_balance_exposed ? "yes" : "no"}.</p></div><div class="card"><h2>Simulated flow</h2>${ledger}</div>`;
});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path != "/api/shadow":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 10000:
            self._send(413, b'{"error":"payload too large"}', "application/json")
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = shadow(payload)
        except ValueError as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        except Exception:
            self._send(400, b'{"error":"could not run the simulation"}', "application/json")
            return
        self._send(200, json.dumps(result).encode(), "application/json")

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    host = "0.0.0.0" if "--lan" in sys.argv else HOST_LOCAL
    server = ThreadingHTTPServer((host, PORT), Handler)
    print("TollDirect shadow test — simulation only")
    print(f"Open http://{HOST_LOCAL}:{PORT}")
    if host == "0.0.0.0":
        print("LAN mode is on. Use this computer's private Wi-Fi address from the iPhone.")
        print("Do not forward this port to the internet.")
    server.serve_forever()


if __name__ == "__main__":
    main()
