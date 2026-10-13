# TollDirect — Event-triggered direct passenger toll payment

Simulation only. No live payments. No external contact without owner approval.

Principle: one toll crossing, one passenger payment, direct to the vehicle’s E-ZPass account, no driver funding.

## Architecture

TollDirect is not a driver reimbursement product. It is a proposed settlement layer between three parties that already exist:

1. The transportation network company holds the passenger’s trip payment method and knows when a trip is active.
2. MassDOT / E-ZPass MA records the gantry crossing and posts the toll to the vehicle’s account.
3. A licensed payment provider, if required, moves the passenger-funded toll portion to that E-ZPass account under a written arrangement.

TollDirect does not collect card numbers, does not hold passenger funds, and does not call private Uber, Lyft, or E-ZPass APIs. Those integrations do not exist in public form and are not assumed.

## Event-to-payment sequence

1. Active trip. Uber or Lyft already has an authorized passenger payment method for the trip. No extra app or passenger action.
2. Crossing. The vehicle passes a Massachusetts gantry. Detection is an authorized E-ZPass / MassDOT record, matched to the TNC’s active trip by vehicle, plate, transponder, and time. A TNC GPS estimate may flag the event early, but it is not the official amount.
3. Official amount. The eligible toll is the amount MassDOT posts, including any later commercial-rate adjustment. Until that record exists, the amount is pending.
4. Passenger charge. The TNC charges only the passenger’s existing trip payment method for that toll portion. One crossing ID, one charge.
5. E-ZPass credit. The confirmed passenger funds are credited to the vehicle’s registered E-ZPass MA account through an approved settlement path. The driver is not paid and does not replenish.
6. Reconciliation. Crossing ID, trip ID, passenger charge ID, and E-ZPass credit ID must match. A commercial upcharge adjusts the same record. It does not create a second passenger charge or a driver payout.

Immediate payment at the exact second of crossing is not required and is not available from published systems.

## Why delay is the design, not a failure

Official timing found:

- Mass.gov’s own sample shows Exit Date Time 21 September 2019 and Post Date 24 September 2019, about three days later. Source: https://www.mass.gov/info-details/toll-payment-options
- A 2018 MassDOT Office of the Administrative Law Judge report stated that tolls are not posted in real time, that about 20 percent of images need manual review, and that there is a two-to-five-day image-review and trip-building period. Source: https://www.mass.gov/doc/alj-annual-report-2018/download
- A Pay By Plate invoice is mailed about 7–10 business days after the trip is processed. Source: https://www.mass.gov/info-details/toll-payment-options
- The rideshare commercial-rate upcharge can take up to two weeks. Source: https://www.ezdrivema.com/rideshare

No official 24-hour or 48-hour grace period for an insufficient E-ZPass MA balance was found. EZDriveMA terms say that if the prepaid balance falls to or below $0.00, continued use results in a Pay By Plate invoice to the registered owner, possibly at a higher rate and with fees. Manual replenishment requires a positive balance at all times. Source: https://www.ezdrivema.com/documentation/TermsConditions.pdf

Pay By Plate penalties, from the EZDriveMA fee schedule and 700 CMR 7.05:

- First invoice: 30 days to pay, no late fee in days 1–30
- Past-due invoice: 30 days; $1 per overdue toll in days 31–60
- Notice of non-payment: 30 days; another $1 per toll in days 61–90
- Notice of liability: due immediately after 90 days; another $1 per toll plus a $20 RMV/DMV fee; license or registration non-renewal may follow
- Mailed invoice fee: $0.60
- Cap: fines, fees, and penalties not to exceed $500 per year per registered vehicle

Sources: https://www.ezdrivema.com/Fee-Schedule and https://www.law.cornell.edu/regulations/massachusetts/700-CMR-7-05

## Settlement design that does not use the driver

Because the official post arrives days later, the intended production sequence is:

1. Hold the crossing against the active trip.
2. When the official toll record posts, charge the passenger’s existing trip method.
3. Credit the vehicle’s E-ZPass account before or with that post, so the passenger toll never draws the driver’s prepaid balance.
4. If MassDOT cannot credit before the post, the written arrangement must protect the driver from a zero-balance Pay By Plate invoice and from penalties for that passenger toll. No such protection exists today.
5. A later commercial-rate adjustment updates the same settlement. It does not create a second charge.
6. Uber, Lyft, and the driver do not advance the toll. The passenger is the only funding source.

This requires approvals that do not exist: a TNC settlement change, a MassDOT account-credit path, and a licensed payment provider if funds move between them.

## Failure handling

- Delayed official record: status stays Pending. No driver replenishment. No estimated charge treated as final.
- Passenger charge fails: retry through the TNC. Do not charge a second method. Do not ask the driver to pay.
- E-ZPass credit fails: do not mark Sent. Reverse or hold the passenger charge according to the TNC agreement. Do not fall back to the driver’s bank.
- Duplicate: the crossing ID blocks a second passenger charge and a second E-ZPass credit. A driver reimbursement for the same crossing is suppressed.
- Refund or correction: reverse the passenger charge and the E-ZPass credit together, or net them on the next official adjustment.
- Penalty risk: if a zero balance would produce Pay By Plate before the credit lands, the trip is flagged. TollDirect cannot prevent that penalty without a MassDOT written waiver or a pre-posting credit path.

## Integrations required

- Uber or Lyft: active-trip match, existing passenger payment authorization, toll-portion charge, and suppression of the driver reimbursement. No public API for this was found.
- MassDOT / E-ZPass MA: authorized crossing feed, official amount including commercial adjustment, and a credit to the vehicle’s account. No public funding API was found. Account assignment needs written consent.
- Licensed payment provider: only if funds must move outside the TNC’s existing passenger charge. TollDirect does not process cards itself.

## Feasibility

Existing: gantry read, delayed post, passenger fare that includes a toll, driver reimbursement, commercial upcharge on the driver account.

Not available: real-time third-party credit, institutional funding of a driver account, or a confirmed grace period after a zero balance.

Required before any live use: written MassDOT approval, one TNC settlement change, duplicate controls, and a licensed payment path. Until then the prototype remains simulated.

## Simulated proof of concept

`index.html` demonstrates the sequence with sample events, delayed posting, a failed credit, and a commercial-rate adjustment. Every payment state is labeled simulation. No credentials are collected and no money moves.

## Core payment-routing modules (simulation)

Added in the next engineering phase. These modules formalize the rules the durable engine already enforces. They do not process money and do not replace the existing 21-test engine.

| Module | Role |
| --- | --- |
| `core/matching.py` | Matches one crossing to exactly one active passenger trip by vehicle and time. Zero or multiple trips produce no charge. |
| `core/toll.py` | Accepts only a recorded official amount. Missing, zero, or negative amounts are never invented. Commercial change is a delta. |
| `core/routing.py` | Plans a passenger-funded route whose only destination is the vehicle E-ZPass account. No driver bank field exists. |
| `core/reconciliation.py` | Classifies unmatched, pending, charged-pending-credit, reconciled, failed, refunded, disputed, and insufficient-funds-risk. |
| `core/coordinator.py` | Wires the modules for decision tests. Confirmation requires both a passenger charge id and an E-ZPass credit id. |

A simulated charge is not a confirmed E-ZPass credit. Confirmation is a separate state and is only set after a credit identifier exists.

### Transaction lifecycle

1. Crossing detected.
2. Match: exactly one active trip, or unresolved.
3. Official amount pending, or verified recorded amount.
4. Route planned to vehicle E-ZPass only.
5. Simulated passenger charge.
6. Simulated E-ZPass credit.
7. Reconciled only when charge id and credit id both exist and amounts match.
8. Failure, refund, dispute, or insufficient-funds risk stays visible and is not converted into driver funding.

### External integrations still required

These are not implemented and are not assumed to exist:

- Uber or Lyft: authorized active-trip feed, existing passenger payment method, one toll-portion charge, suppression of driver reimbursement.
- MassDOT / E-ZPass MA: authorized crossing feed, official posted amount including commercial adjustment, and a credit path to the vehicle account that does not debit the driver first.
- Licensed payment provider: only if funds must move outside the TNC’s existing passenger charge.
- Written approvals from each party before any live use.

Until those approvals exist, every event remains simulated.

## Provider-independent adapter boundary

The core settlement rules do not import a provider. Future authorized adapters implement four contracts in `backend/tolldirect/adapters/contracts.py`:

1. `TripEventSource` — active passenger trip events. No driver payment method.
2. `TollCrossingSource` — gantry records and later official posted amounts.
3. `PassengerPaymentConfirmation` — charge and confirmation against the passenger method already authorized for the trip.
4. `EzPassCreditConfirmation` — credit and confirmation to the vehicle E-ZPass account only.

`IntegrationRunner` applies these events in arrival order. Delayed posts, duplicates, out-of-order records, partial failures, retries, refunds, and commercial adjustments are handled without a second passenger charge. A simulated confirmation is not a real E-ZPass settlement.

### Requirements that simulation cannot establish

- Whether Uber or Lyft will expose an authorized active-trip feed and charge the existing passenger method for a toll portion.
- Whether MassDOT / E-ZPass MA will accept a credit to a vehicle account without first debiting the prepaid balance.
- Official posting latency, and whether a credit can be applied before or with the toll post.
- Whether a partner arrangement can prevent Pay By Plate or penalties when the account is at zero at the time of travel.
- Commercial-rate adjustment notification and timing.
- Provider idempotency, refund, and dispute behavior.
- Consent and authorization to associate a vehicle with an E-ZPass account.

Until those capabilities are confirmed in writing, every event remains simulated.

## Payment timing and zero-balance protection

`core/timing.py` separates four states. Only the last changes the E-ZPass balance:

1. Authorized — passenger method is authorized for the trip. Balance unchanged.
2. Captured — passenger charge is captured. Balance unchanged.
3. Settled — passenger funds are settled to the payment path. Balance unchanged.
4. Confirmed E-ZPass credit — the vehicle account balance increases.

A confirmed credit cannot be timestamped before capture. Real-time external E-ZPass credit is not verified and is not assumed.

Three proposed timings are modeled for a zero starting balance:

- Before crossing: only covers the toll if capture can complete before the gantry. Not an E-ZPass capability.
- At crossing: same constraint. Not an E-ZPass capability.
- After official post: matches known delayed posting. If the account is at zero at travel, the toll can be assessed before the credit lands. This exposure is reported. No driver replenishment is introduced.

Run `python3 demo_timing.py` from `backend/` for the timestamped demonstration.

### Timing requirements a future E-ZPass integration must satisfy

- A credit must be confirmable to the vehicle account without debiting the driver first.
- If the account can be at zero at travel, the credit must be effective before the toll is assessed, or MassDOT must waive Pay By Plate and penalties for that passenger toll.
- The integration must expose credit confirmation separately from passenger authorization, capture, and settlement.
- No such real-time or pre-assessment credit path has been verified.
