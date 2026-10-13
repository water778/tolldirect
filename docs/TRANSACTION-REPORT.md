# Transaction report — Tobin Bridge, $3.50

Source: `backend/poc_demo.py` on commit `8736148`.  
All values are synthetic. No external system was contacted.

## Summary

| Item | Value |
| --- | --- |
| Crossing | `GX-TOBIN-2201` |
| Location | Tobin Bridge, Massachusetts |
| Vehicle | `V-441`, plate `MA-441`, tag `TAG-77` |
| Passenger trip | `T-UBER-100`, Uber |
| Passenger method | `pm_passenger_ok` (synthetic token, not a card) |
| Official toll | 350 cents ($3.50), recorded after the crossing |
| Destination | E-ZPass `EZ-MA-441`, ending `4821` |
| Passenger charge | `PCH-0001`, 350 cents |
| E-ZPass credit | `EZC-0001`, 350 cents |
| Final status | Reconciled |
| Driver bank account | Not present |
| Driver-funded recharge | Not used |

## Flow

1. Crossing detected for vehicle `V-441`.
2. Exactly one active passenger trip matched: `T-UBER-100`.
3. Vehicle mapped to E-ZPass `EZ-MA-441`.
4. Official amount was not yet posted, so no charge was created.
5. A duplicate of the same crossing arrived and was blocked. The original settlement was left unchanged.
6. Official amount of 350 cents posted.
7. The passenger method already authorized for the trip was charged once.
8. The same 350 cents was credited to the vehicle E-ZPass account.
9. Reconciliation balanced: 350 cents charged, 350 cents credited.

## Ledger for this crossing

| Entry | Kind | Amount | Detail |
| --- | --- | ---: | --- |
| LED-000001 | crossing_detected | 0 | Tobin Bridge, vehicle V-441 |
| LED-000002 | matched | 0 | trip T-UBER-100, E-ZPass EZ-MA-441 ending 4821 |
| LED-000003 | awaiting_amount | 0 | official post not yet available |
| LED-000007 | duplicate_blocked | 0 | crossing already open |
| LED-000008 | passenger_charged | 350 | PCH-0001 |
| LED-000009 | credited_to_ezpass | 350 | EZC-0001 |
| LED-000010 | reconciled | 350 | charge PCH-0001, credit EZC-0001 |

## How driver funding is prevented

- The payment destination type is `ezpass_account` only. A bank destination is rejected by the routing contract.
- The passenger method is the method already authorized for the trip. No separate passenger action is requested.
- If the passenger charge fails, the settlement stays `failed_unresolved`. The engine does not charge the driver or the rideshare platform.
- If the E-ZPass credit fails after a successful passenger charge, the passenger is not charged again on retry. The credit is retried against the same account.
- An E-ZPass balance of zero is recorded as exposure. It is not covered by a driver recharge.

## How duplicate charges are prevented

- The first event for a crossing opens one settlement.
- A repeated crossing with the same identifier is recorded as `duplicate_blocked` and does not create a second charge.
- Passenger charge and E-ZPass credit each use a durable idempotency claim.
- A commercial-rate adjustment charges only the difference, not the full toll again.
- Reconciliation reports charged cents, credited cents, unresolved crossings, and blocked duplicates.

## Boundary

`passenger_charged` and `credited_to_ezpass` are simulated identifiers. A simulated credit is not a confirmed MassDOT posting and is not evidence that E-ZPass accepts real-time external credits.
