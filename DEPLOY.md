# TollDirect simulation deployment

Read-only. Synthetic data only. No real payments.

## Local

```
cd backend
python3 seed_demo.py
python3 -m unittest discover -s tests -v
```

To enable the local read-only dashboard:

```
export TOLLDIRECT_DEMO_PASSWORD=your-local-only-password
```

Never commit the password or set it on a public deployment.

## Cloud

No public deployment of the dashboard is authorized.

- Health: `GET /health` — public, no transaction data
- Dashboard: `GET /` — disabled unless TOLLDIRECT_DEMO_PASSWORD is set in the environment (local simulation only)
- Demo user: `demo`

POST, PUT, and DELETE are rejected. There are no payment or admin controls.

The bundled SQLite file is `backend/tolldirect/data/demo-readonly.db`.
