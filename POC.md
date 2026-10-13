# TollDirect proof of concept

Simulation only. No real payments and no external connections.

This is the consolidated technical prototype. It uses the existing settlement engine, matching rules, payment-stage model, and reconciliation ledger.

## Run on Windows

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/).
2. During setup, enable **Add python.exe to PATH**.
3. Open Command Prompt or PowerShell.
4. Go to the `backend` folder of this repository.
5. Run:

```bat
python poc_demo.py
```

If `python` is not found, try:

```bat
py -3 poc_demo.py
```

The demonstration writes a local SQLite file under the Windows temporary directory. It does not need a network connection.

## Run the tests

```bat
cd backend
python -m unittest discover -s tests -v
```

## What the demonstration shows

- An Uber passenger trip, vehicle `V-441`, and a Tobin Bridge crossing.
- Automatic match to E-ZPass account `EZ-MA-441`, ending `4821`.
- One passenger-funded charge of 350 cents after the official amount posts.
- Destination is the vehicle E-ZPass account. No driver bank account is used.
- A duplicate crossing is blocked.
- A failed passenger charge stays unresolved and is not replaced with driver funds.
- Authorization, capture, and settlement do not change the E-ZPass balance.
- A proposed credit before assessment is labeled unverified.
- A credit after the official post leaves a zero-balance exposure. No driver replenishment is added.
- The full append-only ledger is printed.

## Implemented in simulation

- Trip-to-crossing matching by vehicle and active window
- Recorded-amount verification, with no invented toll
- Passenger charge and E-ZPass credit as separate simulated steps
- Exactly-once claims, duplicate blocking, refund, and commercial-rate delta
- Durable SQLite ledger and restart-safe settlement state
- Payment-stage timing and zero-balance exposure detection
- Provider contracts for a future authorized adapter

## Not implemented and not assumed

These require written authorization and a real interface. Simulation cannot establish them:

- Uber or Lyft active-trip feed and toll-portion charge on the existing passenger method
- MassDOT / E-ZPass MA crossing feed and official posted amount
- A credit to a vehicle E-ZPass account that does not debit the driver first
- Real-time or pre-assessment external credit
- A waiver of Pay By Plate or penalties when the account is at zero at travel time
- Commercial-rate adjustment notification from the toll authority
- Provider idempotency, refund, and dispute behavior

EZDriveMA customer service stated on 12 October 2026 that funds must be on the account at the time of travel and that the account holder remains responsible for a positive balance. See `EZDRIVEMA-REPLY.md`. No real-time external credit capability has been verified.
