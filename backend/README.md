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

Official Uber and E-ZPass adapters are not implemented. They require written partner access that does not exist.
