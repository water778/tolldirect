# TollDirect — Direct passenger-to-E-ZPass settlement

Simulation only. No external message has been sent. No money moves.

## Actual money flow today

1. The driver’s E-ZPass MA transponder is read at a Massachusetts gantry.
2. MassDOT posts the toll to the driver’s E-ZPass MA account. Posting is not instant.
3. If the driver was providing TNC service, MassDOT uses TNC ride data to upcharge that same driver account to the commercial rate. EZDriveMA says this can take up to two weeks.
4. The driver must already have funded the account with a card, bank account, check, or in-person payment.
5. Uber or Lyft charges the rider once, including the toll portion, and later pays that amount to the driver as a reimbursement.

The passenger’s money reaches the driver. It does not reach E-ZPass. The driver’s personal funds reach E-ZPass first.

## Existing capability

- E-ZPass MA prepaid and commercial prepaid accounts, funded by the account holder.
- Commercial Surety postpaid account, secured by a bond of six months of tolls or $5,000, whichever is greater. Still the account holder’s obligation.
- TNC ride-data exchange so MassDOT can apply the commercial rate.
- Uber and Lyft rider toll charges and driver reimbursements.
- EZDriveMA terms requiring the holder to keep a valid card or bank account, and barring assignment without written consent.

## Technically feasible, but not available

A file-based or API credit from an authorized payer into a named E-ZPass MA account is technically ordinary for a toll back office. TransCore already posts charges to named accounts. A credit instruction is a system change, not a new toll technology. It is not offered.

A TNC could also identify the toll portion of a fare and suppress the driver reimbursement. That is an internal settlement change. It is not offered.

## Requires regulatory or contractual approval

- MassDOT written consent to a third-party credit, because the current agreement is with the account holder.
- A MassDOT decision on whether a TNC, TollDirect, or a licensed payment provider may hold or fund a settlement balance.
- A TNC contract change so the toll portion is allocated to E-ZPass MA and not also paid to the driver.
- A licensed payment provider if funds are held or moved between the TNC and MassDOT.
- Treatment of the commercial upcharge, delayed posts, refunds, and Pay By Plate protection.
- Out-of-state E-ZPass tolls are outside an MA-only arrangement.

M.G.L. c. 159A½, from Chapter 187 of the Acts of 2016, requires commercial-rate transponders and TNC data cross-reference. It does not require the TNC to pay MassDOT directly. The current implementation is an upcharge on the driver account.

## Institutional or dedicated settlement account

No published E-ZPass MA institutional funding account or dedicated third-party settlement account was found. The nearest existing products are the commercial prepaid account and the bond-backed commercial surety account. Neither accepts passenger-fare allocation.

## Minimum viable pilot

One TNC, E-ZPass MA only, Massachusetts facilities only, no live money until written approval.

1. MassDOT confirms in writing whether it will discuss a third-party credit path.
2. The TNC confirms it can mark an eligible toll portion and suppress the matching driver reimbursement.
3. A paper reconciliation matches trip, gantry event, commercial upcharge, and proposed credit.
4. MassDOT states the timing required to avoid a Pay By Plate invoice.
5. Only after those written answers: a licensed payment provider and a limited live test.

If MassDOT will not discuss a credit path, the direct model is blocked in Massachusetts.

## Recommended next action

Approve or edit `PARTNERSHIP-INQUIRY.md`, then send it to the EZDriveMA Commercial Department and ask for the MassDOT official responsible for TNC tolls. Do not build more product until that answer exists.
