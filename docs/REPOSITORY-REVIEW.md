# Repository review

Reviewed at commit `8736148` on 12 October 2026. No code behavior was changed for this review.

## Security

- The backend uses the Python standard library only. There is no dependency file and no third-party package.
- No API key, live card, bank account, or E-ZPass credential is stored.
- Passenger methods in the demonstration are synthetic tokens such as `pm_passenger_ok`.
- The routing contract rejects a non-E-ZPass destination, including a driver bank account.
- Failed charges remain unresolved. There is no driver-fund fallback.
- The local read-only dashboard uses a fixed demonstration password, `tolldirect-sim`. That is acceptable only for a local simulation. It is not a production control.
- SQLite files are local demonstration stores. They are not a shared financial system.
- No outbound network call is made by the proof of concept.

## Test coverage

`python -m unittest discover -s tests` reports 58 passing tests.

| Area | Tests |
| --- | ---: |
| End-to-end settlement | 7 |
| Engine verification | 8 |
| Durability and restart | 3 |
| Read-only dashboard | 3 |
| Adapter integration | 7 |
| Routing, matching, toll, reconciliation | 20 |
| Timing and future-adapter contracts | 9 |
| Complete proof of concept | 1 |

Covered: matching, delayed post, duplicate blocking, charge failure, credit failure after charge, refund, commercial-rate delta, restart between charge and credit, zero-balance exposure, and rejection of a driver-bank destination.

Not covered because no real provider exists: live Uber/Lyft event delivery, live MassDOT posting, and a real E-ZPass credit confirmation.

## Reproducibility

- Python 3.10 or newer.
- No pip install step.
- Windows, macOS, and Linux use the same commands from `backend/`.
- `python poc_demo.py` creates a fresh local SQLite file and prints the same settlement outcome.
- Tests use temporary databases, so they do not depend on a previous run.
- The unimplemented real adapter is expected to fail its contract checks. That failure is asserted and is not hidden.

## Remaining limits

- The package demonstrates the proposed rules. It does not demonstrate provider acceptance.
- Real-time external E-ZPass credit remains unverified.
- A public deployment is intentionally not part of this package.
