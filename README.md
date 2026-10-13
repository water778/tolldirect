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
