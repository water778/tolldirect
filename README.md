# TollDirect

Prototype only. Simulation / pending official partner integration.

TollDirect is a proposed event-triggered settlement system. One toll crossing during an active passenger trip produces one passenger payment, credited to the vehicle’s E-ZPass account. The driver does not fund the toll. See `ARCHITECTURE.md`.

This repository does not connect to Uber, Lyft, E-ZPass, banks, cards, or Stripe. No credentials are collected and no money moves.

Open `index.html` for the mobile prototype. The simulated backend is in `backend/`.

EZDriveMA customer service refused a pre-debit credit on 12 October 2026. See `EZDRIVEMA-REPLY.md`. The backend remains simulation only.


## Proof of concept

From the `backend` folder:

```bat
python poc_demo.py
```

See `POC.md` for the Windows steps and the boundary between simulation and required external authorization.


## Demonstration package

- `docs/WINDOWS-DEMO.md` — Windows steps
- `docs/TRANSACTION-REPORT.md` — $3.50 Tobin Bridge report
- `docs/TIMING-COMPARISON.md` — pre-assessment versus delayed credit
- `docs/architecture.svg` — architecture diagram
- `docs/PARTNER-READINESS.md` — draft for a future discussion, not sent
- `docs/FEASIBILITY-MATRIX.md` — implemented, simulated, unverified, required
- `docs/REPOSITORY-REVIEW.md` — security, tests, and reproducibility

Real-time external E-ZPass credit is not verified.


## Local shadow test

From `backend/`, run `python shadow.py`. See `docs/SHADOW-TEST.md` for the private iPhone test. It is not a public deployment.
