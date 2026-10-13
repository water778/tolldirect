# Partner-readiness note

Draft for future discussion. Not sent. TollDirect is not a registered partnership and does not represent MassDOT, E-ZPass MA, Uber, or Lyft.

## Purpose

TollDirect is a proposed settlement mechanism for a toll incurred during an active passenger trip. The passenger’s existing trip payment method would fund the toll. The credit destination would be the E-ZPass account associated with the vehicle. The driver would not advance the toll and would not receive it through a personal bank account.

## What can be demonstrated today

- A synthetic Uber trip matched to a synthetic Tobin Bridge crossing and vehicle E-ZPass account.
- One passenger-funded charge of $3.50 after a recorded official amount.
- Duplicate crossing blocked.
- Failed passenger charge left unresolved, with no driver fallback.
- Authorization, capture, and settlement shown separately from a confirmed simulated credit.
- Zero-balance exposure shown when the credit arrives after the official post.
- Append-only ledger and reconciliation.

## What is not claimed

- Real-time external E-ZPass credits are not currently supported by any verified interface.
- EZDriveMA customer service stated on 12 October 2026 that funds must be on the account at the time of travel and that the account holder remains responsible for a positive balance.
- No Uber, Lyft, or MassDOT system has been connected.
- No money has moved.

## Questions for a future discussion

For MassDOT / E-ZPass MA:

1. Can an authorized party credit a vehicle E-ZPass account without first debiting the driver?
2. Can that credit be effective before the toll is assessed, or is a waiver of Pay By Plate and penalties required for the pending interval?
3. What posting delay, commercial-rate adjustment, refund, and duplicate-handling rules would apply?
4. Which office would review a technical feasibility discussion?

For Uber or Lyft:

1. Can an authorized integration identify the active trip and vehicle at a toll crossing?
2. Can the toll portion be charged once to the passenger method already authorized for the trip?
3. Can that charge be prevented from also reimbursing the driver through the normal payout?

## Suggested next step

A feasibility discussion only. No implementation, account access, or payment authorization is requested by this note.
