# TollDirect backend

Simulation only. No real payments and no external connections.

Passenger payment → TollDirect processing → vehicle-linked E-ZPass account.

The driver does not fund the toll. Uber and Lyft do not fund the toll. A failed passenger charge stays unresolved.

## Run

```
cd backend
python3 demo.py
python3 -m unittest tests.test_end_to_end -v
```

## Modules

- `tolldirect/engine.py` — detect, match, charge, credit, reconcile
- `tolldirect/ledger.py` — append-only audit ledger
- `tolldirect/adapters/base.py` — replaceable TNC, E-ZPass, and payment contracts
- `tolldirect/adapters/synthetic.py` — synthetic data only
- `tolldirect/dashboard.py` — internal monitor

Settlements and the audit ledger are stored in SQLite. A restart between a passenger charge and E-ZPass credit does not create a second charge.

```
cd backend
python3 -m unittest discover -s tests -v
python3 demo.py
python3 control.py
```

Control Center: http://127.0.0.1:8787

Official Uber and E-ZPass adapters are not implemented.

## Core routing modules

- `tolldirect/core/matching.py` — trip-to-toll match
- `tolldirect/core/toll.py` — recorded-amount verification
- `tolldirect/core/routing.py` — E-ZPass-only payment route
- `tolldirect/core/reconciliation.py` — lifecycle and balance
- `tolldirect/core/coordinator.py` — decision wiring for tests

A route is simulated until both a passenger charge id and an E-ZPass credit id exist. The driver bank is not a destination.
