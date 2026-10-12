# TollDirect simulation deployment

Read-only. Synthetic data only. No real payments.

## Local

```
cd backend
python3 seed_demo.py
python3 -m unittest discover -s tests -v
```

## Cloud

The existing Vercel account is used. No new paid service is required.

- Health: `GET /health` — public, no transaction data
- Dashboard: `GET /` — HTTP Basic authentication
- Demo user: `demo`
- Demo password: `tolldirect-sim`

POST, PUT, and DELETE are rejected. There are no payment or admin controls.

The bundled SQLite file is `backend/tolldirect/data/demo-readonly.db`.
